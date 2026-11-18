"""Insight Brief + AI insights.

The Insight Brief is the *only* material the insight model sees:
  * facts     - engine results (value, display string, formula ID), built deterministically
  * quality   - identity checks, restatements, open review items
  * narrative - a few retrieved management passages (RAG, latest report, optional)
  * external  - analyst-provided / connector facts with source and date
The full report is never sent. Every number in the generated text must appear
verbatim in the brief (numeric guard) or the draft is replaced by the
deterministic template, and the UI says why.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.annual.engine import FORMULAS
from app.annual.lineage import fmt_of, metric_name
from app.annual.rag import passage
from app.calculations.engine import run_formula
from app.calculations.formulas import DIFFERENCE
from app.models.domain import utcnow
from app.services import llm
from app.services.workspace import summarize_checks

log = logging.getLogger("fiw.annual.insights")

DISCLAIMER = llm.DISCLAIMER
KPI_KEYS = ["revenue", "ebitda", "ebitda_margin", "profit", "net_margin", "cfo", "capex", "fcf", "cash_conversion",
            "net_debt", "net_debt_to_ebitda", "debt_to_equity", "roe", "interest_cover", "effective_tax_rate"]
GROWTH_KEYS = ["revenue_growth", "ebitda_growth", "profit_growth", "cfo_growth"]
TOPICS = {
    "strategy_outlook": "outlook strategy growth priorities future",
    "segments": "segment performance digital services retail oil to chemicals revenue EBITDA",
    "capex_investment": "capital expenditure investment new energy capacity",
    "risks": "risks challenges headwinds regulatory uncertainty",
}

INSIGHT_SYSTEM = """You are the Insight Agent of a financial analysis platform. You write 4 to 6 concise insights
for an investment committee from the INSIGHT_BRIEF only.

Hard rules:
- Every number you write must be copied exactly from a "display" field or from quoted brief text. Never compute,
  convert, round or combine numbers. If you want a figure that is not in the brief, describe it qualitatively.
- Cite the brief items you used in "refs" (ids such as F3, Q1, N2, X1). Narrative (N) and external (X) items are
  claims by their sources: attribute them ("management states...", "per Tracxn...").
- Flag data-quality caveats (restatements, open review items) when relevant.
Respond with JSON only: {"insights": [{"title": str, "text": str, "refs": [str]}]}"""


# --------------------------------------------------------------------------- #
# Formatting (presentation only)
# --------------------------------------------------------------------------- #
def indian(n: float, decimals: int = 0) -> str:
    neg = n < 0
    s = f"{abs(n):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        whole = f"{head},{tail}"
    out = whole + (f".{frac}" if frac else "")
    return f"-{out}" if neg else out


def display(key: str, v: Optional[float], unit: str = "crore") -> str:
    if v is None:
        return "not computable"
    f = fmt_of(key)
    if f == "percent":
        return f"{v * 100:.1f}%"
    if f == "multiple":
        return f"{v:.2f}x"
    if f == "number":
        return f"{v:.2f}"
    return f"{'-' if v < 0 else ''}₹{indian(abs(v))} {unit}"


# --------------------------------------------------------------------------- #
# Brief
# --------------------------------------------------------------------------- #
def build_brief(ws, include_narrative: bool = True) -> dict:
    m = ws.model
    latest, prior = m["latest"], m["prior"]
    facts: list[dict] = []
    n = 0

    def fact(key: str, period: str, value, formula_id: str | None, name: str | None = None, disp: str | None = None):
        nonlocal n
        n += 1
        facts.append({"id": f"F{n}", "metric": key, "name": name or metric_name(key), "period": period,
                      "value": value, "display": disp or display(key, value, ws.unit), "formula_id": formula_id})

    for key in KPI_KEYS:
        for p in (latest, prior):
            if not p:
                continue
            r = m["per_period"].get(key, {}).get(p)
            if r:
                fact(key, p, r["result"], r["formula_id"])
            elif key in m["values"] and p in m["values"][key]:
                fact(key, p, m["values"][key][p], "SOURCE")
    for key in GROWTH_KEYS:
        r = m["per_period"].get(key, {}).get(latest)
        if r:
            fact(key, latest, r["result"], r["formula_id"], f"{metric_name(key.removesuffix('_growth'))} growth YoY")
    for ratio in ("ebitda_margin", "net_margin"):
        cur = m["per_period"].get(ratio, {}).get(latest)
        pre = m["per_period"].get(ratio, {}).get(prior) if prior else None
        if cur and pre:
            d = run_formula(DIFFERENCE, {"current": cur["result"], "prior": pre["result"]})
            if d.result is not None:
                fact(f"{ratio}_change", latest, d.result, "DIFF_001", f"{metric_name(ratio)} change vs {prior}",
                     f"{d.result * 100:+.1f} pp")
    series = {k: {p: m["values"].get(k, {}).get(p) for p in m["periods"]} for k in ("revenue", "ebitda", "profit")}
    trends = [{"metric": k, "name": metric_name(k),
               "series": [{"period": p, "display": display(k, v, ws.unit)} for p, v in s.items()]}
              for k, s in series.items()]

    summary = summarize_checks(ws.checks)
    ids = m["identities"]
    quality = [
        {"id": "Q1", "text": f"{sum(1 for i in ids if i['matches'])} of {len(ids)} accounting identity checks "
                             "reconcile to the printed statements."},
        {"id": "Q2", "text": f"{len(m.get('restatements', []))} restated comparative figure(s) between reports"
                             + (": " + "; ".join(f"{r['name']} {r['period']} restated from "
                                                 f"{display(r['category'], r['original'], ws.unit)} to "
                                                 f"{display(r['category'], r['restated'], ws.unit)}"
                                                 for r in m.get("restatements", [])[:3]) if m.get("restatements") else "")},
        {"id": "Q3", "text": f"{summary['counts']['REVIEW_REQUIRED']} validation item(s) require review and "
                             f"{summary['counts']['WARNING']} warning(s) are open."},
    ]
    narrative: list[dict] = []
    if include_narrative:
        latest_doc = ws.reports[-1].document.id if ws.reports else None
        latest_doc = max((r.document.id for r in ws.reports), key=ws.report_rank) if ws.reports else latest_doc
        seen = set()
        for topic, q in TOPICS.items():
            for c, score in ws.index.search(q, k=4, kinds={"narrative"}, document_id=latest_doc):
                if c.id in seen or len([x for x in narrative if x["topic"] == topic]) >= 2:
                    continue
                seen.add(c.id)
                narrative.append({"id": f"N{len(narrative) + 1}", "topic": topic, **passage(c, score, 520)})
    external = [{"id": x["id"], "source": x["source"], "as_of": x["as_of"], "title": x["title"], "text": x["text"]}
                for x in ws.external]
    return {"entity": ws.extraction.entity_name, "currency": ws.currency, "unit": ws.unit,
            "periods": m["periods"], "latest": latest, "prior": prior, "facts": facts, "trends": trends,
            "quality": quality, "narrative": narrative, "external": external,
            "composition": {"facts": len(facts), "narrative_passages": len(narrative), "external": len(external),
                            "report_pages_total": sum(len(r.pages) for r in ws.reports),
                            "report_pages_in_brief": len({(x["document"], x["page"]) for x in narrative})}}


# --------------------------------------------------------------------------- #
# Numeric guard (verbatim numbers)
# --------------------------------------------------------------------------- #
_NUM = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> list[str]:
    return [t.replace(",", "").lstrip("+") for t in _NUM.findall(text)]


def verify_verbatim(text: str, allowed_texts: list[str]) -> dict:
    allowed = set()
    for t in allowed_texts:
        for x in _numbers(t):
            allowed.add(x)
            allowed.add(x.lstrip("-"))
    checked, unverified = 0, []
    for tok in _numbers(text):
        bare = tok.lstrip("-")
        try:
            v = float(bare)
        except ValueError:
            continue
        if ("." not in bare and (1990 <= v <= 2100 or v <= 31)):
            continue  # years, FY labels, small counts
        checked += 1
        if bare not in allowed:
            unverified.append(tok)
    return {"checked": checked, "verified": checked - len(unverified), "unverified": unverified,
            "passed": not unverified}


def brief_texts(brief: dict) -> list[str]:
    out = [f["display"] for f in brief["facts"]]
    out += [x["display"] for t in brief["trends"] for x in t["series"]]
    out += [q["text"] for q in brief["quality"]] + [p["text"] for p in brief["narrative"]]
    out += [x["text"] for x in brief["external"]]
    return out


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _f(brief: dict, metric: str, period: str | None = None) -> dict | None:
    period = period or brief["latest"]
    return next((f for f in brief["facts"] if f["metric"] == metric and f["period"] == period), None)


def template_insights(brief: dict) -> list[dict]:
    L, P = brief["latest"], brief["prior"]
    out = []

    def g(metric, period=None):
        f = _f(brief, metric, period)
        return (f["display"], f["id"]) if f else ("not computable", None)

    rev, r1 = g("revenue")
    rg, r2 = g("revenue_growth")
    eb, r3 = g("ebitda")
    eg, r4 = g("ebitda_growth")
    out.append({"title": "Growth", "refs": [x for x in (r1, r2, r3, r4) if x],
                "text": f"Revenue from operations was {rev} in {L} ({rg} year on year); EBITDA was {eb} ({eg})."})
    em, r5 = g("ebitda_margin")
    emp, r6 = g("ebitda_margin", P)
    emc, r7 = g("ebitda_margin_change")
    nm, r8 = g("net_margin")
    out.append({"title": "Profitability", "refs": [x for x in (r5, r6, r7, r8) if x],
                "text": f"EBITDA margin was {em} in {L} versus {emp} in {P} ({emc}); net margin was {nm}."})
    cfo, r9 = g("cfo")
    fcf, r10 = g("fcf")
    cc, r11 = g("cash_conversion")
    out.append({"title": "Cash generation", "refs": [x for x in (r9, r10, r11) if x],
                "text": f"Operating cash flow was {cfo} and free cash flow (CFO plus capex as printed) was {fcf}; "
                        f"cash conversion of EBITDA was {cc}."})
    nd, r12 = g("net_debt")
    nde, r13 = g("net_debt_to_ebitda")
    de, r14 = g("debt_to_equity")
    out.append({"title": "Balance sheet", "refs": [x for x in (r12, r13, r14) if x],
                "text": f"Net debt stood at {nd}, or {nde} EBITDA, with debt to equity of {de}."})
    q = brief["quality"]
    out.append({"title": "Data quality", "refs": [x["id"] for x in q],
                "text": " ".join(x["text"] for x in q)})
    for p in brief["narrative"][:1]:
        quote = p["text"][:260].rsplit(" ", 1)[0]
        out.append({"title": "Management context (retrieved)", "refs": [p["id"]],
                    "text": f"From the report ({p['document']}, p.{p['page']}): “{quote} ...”"})
    for x in brief["external"][:2]:
        out.append({"title": x["title"] or "External context", "refs": [x["id"]],
                    "text": f"Per {x['source']}{' (' + x['as_of'] + ')' if x['as_of'] else ''}: {x['text']}"})
    return out


def generate(ws, include_narrative: bool = True) -> dict:
    from app.annual.pipeline import record_exposure

    provider = llm.get_provider()
    brief = build_brief(ws, include_narrative)
    allowed = brief_texts(brief)
    note = None
    insights = None
    if provider.live and hasattr(provider, "_chat"):
        payload = json.dumps({k: brief[k] for k in ("entity", "currency", "unit", "periods", "facts", "trends",
                                                    "quality", "narrative", "external")}, ensure_ascii=False)
        record_exposure(ws, provider, "AI insights (Insight Brief only)", chars=len(payload),
                        pages=[{"document": p["document"], "page": p["page"]} for p in brief["narrative"]],
                        chunks=[p["chunk_id"] for p in brief["narrative"]], content=payload)
        try:
            msg = provider._chat([{"role": "system", "content": INSIGHT_SYSTEM},
                                  {"role": "user", "content": "INSIGHT_BRIEF:\n" + payload}],
                                 max_tokens=1500, temperature=0.2, response_format={"type": "json_object"})
            data = json.loads(msg.content or "{}")
            valid_ids = {f["id"] for f in brief["facts"]} | {q["id"] for q in brief["quality"]} | \
                        {p["id"] for p in brief["narrative"]} | {x["id"] for x in brief["external"]}
            insights = [{"title": str(i.get("title", ""))[:80], "text": str(i.get("text", "")),
                         "refs": [r for r in i.get("refs", []) if r in valid_ids]}
                        for i in data.get("insights", []) if isinstance(i, dict) and i.get("text")]
            if not insights:
                raise ValueError("empty insight list")
        except Exception as exc:
            log.warning("AI insights failed, using deterministic template: %s", exc)
            note = f"AI provider unavailable ({exc.__class__.__name__}) - deterministic insights shown."
            insights = None
    if insights is not None:
        check = verify_verbatim(" ".join(i["text"] for i in insights), allowed)
        if not check["passed"]:
            note = (f"AI draft contained {len(check['unverified'])} figure(s) not found in the Insight Brief "
                    f"({', '.join(check['unverified'][:3])}); replaced with the deterministic insights.")
            insights = None
    if insights is None:
        insights = template_insights(brief)
        source = "deterministic template"
    else:
        source = f"{provider.name} ({provider.model})"
    text = " ".join(i["text"] for i in insights)
    check = verify_verbatim(text, allowed)
    ws.commentary = {
        "text": text, "insights": insights, "numeric_check": check, "note": note, "provider": provider.name,
        "model": provider.model, "source": source, "generated_at": utcnow(),
        "label": "AI insights generated from the Insight Brief (engine facts + retrieved passages + external context).",
        "disclaimer": DISCLAIMER, "brief": brief,
    }
    ws.audit.record("ai", "insights.generated", f"{len(insights)} insights from the Insight Brief ({source})",
                    agent="Insight Agent", details={"numeric_check": check, "note": note,
                                                    "brief_composition": brief["composition"]})
    return ws.commentary
