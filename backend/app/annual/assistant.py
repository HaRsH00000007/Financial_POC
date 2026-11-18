"""RAG finance assistant for annual-report workspaces.

Two kinds of tools, both deterministic:
* engine tools  - KPIs, metric values, calculation lineage, trends, open checks
* retrieval     - ``search_report`` returns the top passages (with page refs) from the
                  BM25 index; only those passages are shown to the model, and each
                  retrieval is logged in the AI exposure ledger.
Numbers in the answer must appear verbatim in the tool results.
"""
from __future__ import annotations

import json
import logging
import re

from app.annual.engine import FORMULAS
from app.annual.insights import display, verify_verbatim
from app.annual.lineage import build_lineage, metric_name
from app.annual.rag import passage
from app.annual.taxonomy import BY_KEY
from app.services import llm
from app.services.workspace import summarize_checks

log = logging.getLogger("fiw.annual.assistant")

METRICS = sorted(k for k in FORMULAS if not k.endswith(("_difference", "_tieout"))) + \
    sorted(k for k, c in BY_KEY.items() if c.kind == "input")

SYSTEM = """You are the finance assistant for an annual-report analysis workspace (multi-year, consolidated).
- Never do arithmetic. Get every figure from the engine tools and quote their "display" strings exactly.
- For qualitative questions (strategy, segments, risks, outlook, governance) call search_report and answer only
  from the returned passages, citing them as (document, p.N). If the passages do not answer it, say so.
- Name the formula ID when explaining a calculation. Mention INCOMPLETE values or open review items plainly.
- Be concise."""


def _latest(ws) -> str:
    return ws.model["latest"]


def get_kpis(ws, period: str | None = None) -> dict:
    p = period or _latest(ws)
    out = {"period": p, "metrics": {}}
    for k in ["revenue", "ebitda", "ebitda_margin", "profit", "net_margin", "cfo", "fcf", "net_debt",
              "net_debt_to_ebitda", "roe", "revenue_growth"]:
        r = ws.model["per_period"].get(k, {}).get(p)
        if r:
            out["metrics"][k] = {"name": metric_name(k), "display": display(k, r["result"], ws.unit),
                                 "status": r["status"], "formula_id": r["formula_id"]}
    return out


def get_metric(ws, metric: str, period: str | None = None) -> dict:
    p = period or _latest(ws)
    lin = build_lineage(ws, metric, p)
    t = lin["tree"]
    return {"metric": metric, "name": t["name"], "period": p, "display": display(metric, t["value"], ws.unit),
            "status": t["status"], "formula_id": (t.get("formula") or {}).get("formula_id"),
            "formula": (t.get("formula") or {}).get("expression"), "source_pages": lin["pages"],
            "source_documents": lin["documents"]}


def explain_calculation(ws, metric: str, period: str | None = None) -> dict:
    p = period or _latest(ws)
    lin = build_lineage(ws, metric, p)
    t = lin["tree"]
    return {"metric": metric, "name": t["name"], "period": p, "display": display(metric, t["value"], ws.unit),
            "status": t["status"], "formula_id": (t.get("formula") or {}).get("formula_id"),
            "formula": (t.get("formula") or {}).get("expression"),
            "inputs": [{"name": c["name"], "period": c["period"], "display": display(c["metric"], c["value"], ws.unit),
                        "status": c["status"]} for c in t["children"]][:12],
            "source_documents": lin["documents"], "source_pages": lin["pages"]}


def get_trend(ws, metric: str) -> dict:
    s = ws.model["values"].get(metric)
    if s is None:
        return {"error": f"Unknown metric '{metric}'"}
    return {"metric": metric, "name": metric_name(metric),
            "series": [{"period": p, "display": display(metric, s.get(p), ws.unit)} for p in ws.model["periods"]]}


def review_items(ws) -> dict:
    open_checks = [c for c in ws.checks if c.status.value != "VALID" and not c.resolved]
    return {"summary": summarize_checks(ws.checks),
            "open_items": [{"status": c.status.value, "title": c.title} for c in open_checks][:12],
            "restatements": [{"name": r["name"], "period": r["period"],
                              "original": display(r["category"], r["original"], ws.unit),
                              "restated": display(r["category"], r["restated"], ws.unit),
                              "earlier_report": r["original_document"], "later_report": r["restated_document"]}
                             for r in ws.model.get("restatements", [])]}


def search_report(ws, query: str, k: int = 4) -> dict:
    hits = ws.index.search(query, k=min(max(int(k), 1), 6))
    return {"query": query, "retriever": "BM25", "passages": [passage(c, s) for c, s in hits]}


TOOLS = {
    "get_kpis": (get_kpis, "Headline KPIs for a fiscal year (default latest).",
                 {"period": {"type": "string", "description": "e.g. FY2026"}}),
    "get_metric": (get_metric, "Value, status and formula of one metric for a fiscal year.",
                   {"metric": {"type": "string", "enum": METRICS}, "period": {"type": "string"}}),
    "explain_calculation": (explain_calculation, "Formula, inputs and source pages for a metric.",
                            {"metric": {"type": "string", "enum": METRICS}, "period": {"type": "string"}}),
    "get_trend": (get_trend, "Multi-year series of a metric.", {"metric": {"type": "string", "enum": METRICS}}),
    "review_items": (review_items, "Open validation items and restatements.", {}),
    "search_report": (search_report, "Retrieve passages from the annual reports (BM25) for qualitative questions.",
                      {"query": {"type": "string"}, "k": {"type": "integer"}}),
}


def call_tool(ws, name: str, args: dict) -> dict:
    if name not in TOOLS:
        return {"error": f"Unknown tool {name}"}
    try:
        return TOOLS[name][0](ws, **(args or {}))
    except Exception as exc:
        return {"error": str(exc)}


def _citations(calls: list[dict]) -> list[dict]:
    out, seen = [], set()
    for c in calls:
        for p in (c["result"] or {}).get("passages", []) if isinstance(c["result"], dict) else []:
            if p["chunk_id"] not in seen:
                seen.add(p["chunk_id"])
                out.append(p)
    return out


def _period(ws, q: str) -> str | None:
    m = re.search(r"fy\s?'?(20)?(\d{2})\b", q)
    if m:
        key = f"FY20{m.group(2)}"
        return key if key in ws.model["periods"] else None
    return None


def _metric(q: str) -> str | None:
    aliases = {"revenue": "revenue", "sales": "revenue", "turnover": "revenue", "ebitda margin": "ebitda_margin",
               "ebitda": "ebitda", "net margin": "net_margin", "profit": "profit", "pat": "profit",
               "net income": "profit", "free cash": "fcf", "fcf": "fcf", "operating cash": "cfo", "cfo": "cfo",
               "capex": "capex", "net debt to ebitda": "net_debt_to_ebitda", "net debt": "net_debt",
               "debt to equity": "debt_to_equity", "leverage": "net_debt_to_ebitda", "roe": "roe",
               "return on equity": "roe", "interest cover": "interest_cover", "tax rate": "effective_tax_rate",
               "current ratio": "current_ratio", "cash conversion": "cash_conversion", "total assets": "total_assets"}
    for a in sorted(aliases, key=len, reverse=True):
        if a in q:
            return aliases[a]
    return None


def offline_answer(ws, question: str) -> dict:
    q = question.lower()
    calls: list[dict] = []

    def tool(name, **args):
        res = call_tool(ws, name, args)
        calls.append({"tool": name, "args": args, "result": res})
        return res

    metric, period = _metric(q), _period(ws, q)
    qualitative = any(w in q for w in ["why", "strategy", "segment", "risk", "outlook", "plan", "guidance",
                                       "management", "what does", "jio", "retail", "o2c", "energy", "dividend policy"])
    if any(w in q for w in ["review", "restat", "issue", "check", "flag"]):
        r = tool("review_items")
        lines = [f"- **{i['status'].replace('_', ' ')}** - {i['title']}" for i in r["open_items"]] or ["- none"]
        rs = [f"- {x['name']} {x['period']}: {x['original']} ({x['earlier_report']}) -> {x['restated']} "
              f"({x['later_report']})" for x in r["restatements"]]
        answer = "Open validation items:\n" + "\n".join(lines) + ("\n\nRestatements:\n" + "\n".join(rs) if rs else "")
    elif metric and any(w in q for w in ["trend", "over the years", "history", "each year", "multi-year"]):
        r = tool("get_trend", metric=metric)
        answer = f"**{r['name']}** by fiscal year:\n" + "\n".join(f"- {x['period']}: {x['display']}" for x in r["series"])
    elif metric and any(w in q for w in ["calculat", "formula", "how is", "how was", "derive", "trace", "explain"]):
        r = tool("explain_calculation", metric=metric, period=period)
        inputs = "\n".join(f"- {i['name']} ({i['period']}): {i['display']}" for i in r["inputs"])
        answer = (f"**{r['name']} ({r['period']}) = {r['display']}** - {r['status']}.\n\nFormula `{r['formula_id']}`: "
                  f"`{r['formula']}`\n\n{inputs}\n\nSource: {', '.join(r['source_documents'])}, pages "
                  f"{', '.join(map(str, r['source_pages']))}.")
    elif metric and not qualitative:
        r = tool("get_metric", metric=metric, period=period)
        answer = (f"**{r['name']} ({r['period']}): {r['display']}** - {r['status']}, formula "
                  f"`{r['formula_id']}` (`{r['formula']}`).")
    elif qualitative or not metric:
        r = tool("search_report", query=question, k=3)
        if r["passages"]:
            answer = "Most relevant passages from the reports (retrieved, not summarized - offline mode):\n\n" + \
                     "\n\n".join(f"> {p['text'][:420]} ...\n\n- *{p['document']}, p.{p['page']}*" for p in r["passages"])
        else:
            answer = "No relevant passage was found in the reports."
    else:
        r = tool("get_kpis", period=period)
        answer = "Verified KPIs:\n" + "\n".join(f"- {v['name']}: {v['display']}" for v in r["metrics"].values())
    return {"answer": answer, "tool_calls": calls}


def live_answer(ws, provider, question: str, history: list[dict]) -> dict:
    from app.annual.pipeline import record_exposure

    tools = [{"type": "function", "function": {"name": n, "description": d,
                                                "parameters": {"type": "object", "properties": p}}}
             for n, (_, d, p) in TOOLS.items()]
    messages = [{"role": "system", "content": SYSTEM}]
    messages += [{"role": h["role"], "content": h["content"]} for h in history[-8:]
                 if h.get("role") in ("user", "assistant") and h.get("content")]
    messages.append({"role": "user", "content": question})
    calls: list[dict] = []
    for _ in range(6):
        msg = provider._chat(messages, tools=tools, tool_choice="auto", max_tokens=1500)
        if not msg.tool_calls:
            return {"answer": (msg.content or "").strip(), "tool_calls": calls}
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
                out = call_tool(ws, tc.function.name, args)
            except (json.JSONDecodeError, ValueError) as exc:
                args, out = {}, {"error": f"Invalid tool arguments: {exc}"}
            content = json.dumps(out, default=str, ensure_ascii=False)
            if tc.function.name == "search_report" and out.get("passages"):
                record_exposure(ws, provider, "assistant retrieval (top passages only)", chars=len(content),
                                pages=[{"document": p["document"], "page": p["page"]} for p in out["passages"]],
                                chunks=[p["chunk_id"] for p in out["passages"]], content=content)
            calls.append({"tool": tc.function.name, "args": args, "result": out})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
    return {"answer": "I could not complete the analysis within the tool-call limit.", "tool_calls": calls}


def answer(ws, question: str, history: list[dict]) -> dict:
    provider = llm.get_provider()
    note = None
    if provider.live and hasattr(provider, "_chat"):
        try:
            out = live_answer(ws, provider, question, history)
        except Exception as exc:
            out = offline_answer(ws, question)
            note = f"AI provider error ({exc.__class__.__name__}); answered by the offline assistant."
    else:
        out = offline_answer(ws, question)
    allowed = [json.dumps(c["result"], default=str, ensure_ascii=False) for c in out["tool_calls"]]
    check = verify_verbatim(out["answer"], allowed)
    if not check["passed"] or not out["answer"].strip():
        reason = (f"{len(check['unverified'])} figure(s) not found in tool results ({', '.join(check['unverified'][:3])})"
                  if not check["passed"] else "an empty answer")
        out = offline_answer(ws, question)
        check = verify_verbatim(out["answer"], [json.dumps(c["result"], default=str, ensure_ascii=False)
                                                for c in out["tool_calls"]])
        note = f"The AI answer contained {reason}; replaced with the deterministic answer."
    ws.audit.record("ai", "assistant.answer", f"Q: {question[:120]}", agent="Finance Assistant (RAG)",
                    details={"tools": [c["tool"] for c in out["tool_calls"]], "numeric_check": check,
                             "provider": provider.name})
    return {**out, "citations": _citations(out["tool_calls"]), "numeric_check": check, "provider": provider.name,
            "note": note, "disclaimer": llm.DISCLAIMER}
