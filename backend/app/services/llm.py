"""Probabilistic AI layer behind a provider abstraction.

* ``GroqProvider`` - used when ``GROQ_API_KEY`` is set (Groq via the official
  ``groq`` SDK; model from ``GROQ_MODEL``).
* ``MockProvider`` - deterministic stand-in so the POC always runs offline. It is
  labelled as such everywhere in the UI.

Neither provider is ever asked to compute a financial number. They receive
verified outputs (facts / tool results) and produce language. All numbers in
generated text are checked against the engine's values by the numeric-claim
guard before they are shown.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable

from app.normalization.taxonomy import CATEGORIES
from app.services import finance_tools as ft
from app.services.formatting import fmt_currency, fmt_pct, fmt_period, verify_numeric_claims

log = logging.getLogger("fiw.llm")

DISCLAIMER = "AI-generated content should be reviewed before use in formal financial reporting."

NARRATIVE_SYSTEM = """You are the Synthesis Agent in a finance workbench. You write short, precise
management commentary for CFO-level readers.

Hard rules:
- Every number you write MUST appear in the provided VERIFIED_FACTS (formatted display values or raw
  values). Do not compute, add, subtract, average or round numbers yourself. If a figure you want is not
  in the facts, describe the direction qualitatively instead.
- Percentages in the facts are ratios (0.211 means 21.1%). Percentage-point changes are in change_pp
  (0.029 means 2.9 pp).
- If a metric is INCOMPLETE or not computable, say so plainly; never estimate it.
- 3 to 5 sentences, plain prose, no headings, no bullet points."""

ASSISTANT_SYSTEM = """You are the finance assistant inside the Finance Intelligence Workbench.
You answer questions about one company's trailing-twelve-month (T-12) financial model.

Hard rules:
- You never perform arithmetic on financial figures. Retrieve every number with the provided tools, which
  call the deterministic calculation engine, and quote the returned display values.
- When explaining a calculation, name the formula ID and expression returned by the tool and mention the
  source document/pages.
- If data is missing or a metric is INCOMPLETE, say so and point to the review items. Never guess.
- Be concise: short paragraphs or a compact list. Use the currency formatting from tool results."""


class LLMProvider:
    name = "base"
    model = ""
    live = False

    def suggest_mappings(self, labels: list[str]) -> list[dict]:
        return []

    def classify_document(self, filename: str, sample: str) -> dict:
        t = sample.lower()
        kind = "Monthly income statement (P&L)" if any(
            k in t for k in ["revenue", "sales", "cost of", "ebitda", "net income"]) else "Unrecognized financial document"
        return {"document_type": kind, "method": "keyword heuristic", "confidence": 0.9 if "P&L" in kind else 0.3}

    def narrate(self, facts: dict) -> str:
        raise NotImplementedError

    def assistant(self, ws, question: str, history: list[dict]) -> dict:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Mock provider (offline, deterministic)
# --------------------------------------------------------------------------- #
class MockProvider(LLMProvider):
    name = "Mock AI (offline)"
    model = "rule-based-template-v1"
    live = False

    def narrate(self, facts: dict) -> str:
        k = facts["kpis"]["metrics"]
        mt = facts["margins"]
        ex = facts["expenses"]
        parts = []
        rev = k.get("revenue", {})
        growth = k.get("revenue_growth_yoy", {})
        if rev.get("value") is not None:
            s = f"Over the trailing twelve months ({facts['kpis']['window']}), revenue totaled {rev['display']}"
            s += f", {growth['display']} versus the prior twelve months." if growth.get("value") is not None \
                else "; year-over-year growth is not computable because the source lacks a complete prior-year window."
            parts.append(s)
        else:
            parts.append("T-12 revenue is incomplete, so headline totals cannot be stated until open review items "
                         "are resolved.")
        if k.get("ebitda", {}).get("value") is not None:
            parts.append(f"EBITDA was {k['ebitda']['display']} ({k['ebitda_margin']['display']} margin) and net income "
                         f"{k['net_income']['display']} ({k['net_margin']['display']} net margin).")
        em = mt.get("ebitda_margin", {})
        if em.get("first3") is not None and em.get("last3") is not None:
            direction = "improved" if em["change_pp"] > 0 else "declined" if em["change_pp"] < 0 else "was flat"
            opex = mt.get("operating_expenses_shift")
            revs = mt.get("revenue_shift")
            driver = ""
            if opex is not None and revs is not None:
                driver = (f", as average monthly revenue moved {fmt_pct(revs, True)} while operating expenses "
                          f"moved {fmt_pct(opex, True)}")
            parts.append(f"EBITDA margin {direction} from {fmt_pct(em['first3'])} in the first three months to "
                         f"{fmt_pct(em['last3'])} in the last three ({em['change_pp'] * 100:+.1f} pp){driver}.")
        li = ex.get("largest_increase")
        if li:
            parts.append(f"The fastest-growing cost line was {li['name']} ({fmt_pct(li['first3_to_last3_change'], True)} "
                         f"first-quarter to last-quarter average).")
        open_n = facts["review"]["summary"]["counts"]
        if open_n.get("REVIEW_REQUIRED") or facts["review"]["incomplete_metrics"]:
            parts.append("Some items still require review; affected figures are flagged as incomplete.")
        return " ".join(parts)

    # -- assistant: keyword intent routing onto the same deterministic tools --
    _METRIC_WORDS = [
        ("ebitda margin", "ebitda_margin"), ("gross margin", "gross_margin"), ("net margin", "net_margin"),
        ("gross profit", "gross_profit"), ("net income", "net_income"), ("profit", "net_income"),
        ("ebitda", "ebitda"), ("operating expense", "operating_expenses"), ("opex", "operating_expenses"),
        ("cogs", "cogs"), ("cost of goods", "cogs"), ("payroll", "payroll"), ("rent", "rent"),
        ("marketing", "sales_marketing"), ("technology", "technology"), ("software", "technology"),
        ("g&a", "general_admin"), ("administrative", "general_admin"), ("depreciation", "depreciation"),
        ("interest", "interest"), ("tax", "taxes"), ("revenue", "revenue"), ("sales", "revenue"),
    ]

    def _metric(self, q: str, default: str = "revenue") -> str:
        for word, key in self._METRIC_WORDS:
            if word in q:
                return key
        return default

    def assistant(self, ws, question: str, history: list[dict]) -> dict:
        q = question.lower()
        calls: list[dict] = []

        def tool(name: str, **args) -> dict:
            res = ft.call_tool(ws, name, args)
            calls.append({"tool": name, "args": args, "result": res})
            return res

        period = "T12"
        m = re.search(r"\b(20\d{2})-(\d{2})\b", q)
        if m:
            period = m.group(0)

        if any(w in q for w in ["review", "require", "flag", "issue", "missing", "problem", "wrong"]):
            r = tool("review_items")
            items = r["open_items"]
            if not items and not r["incomplete_metrics"]:
                answer = "No open review items. All validation checks are VALID or resolved, and every T-12 metric is deterministic."
            else:
                lines = [f"- **{i['status'].replace('_', ' ')}** - {i['title']}" for i in items[:8]]
                inc = r["incomplete_metrics"]
                answer = f"{len(items)} validation item(s) are open:\n" + "\n".join(lines)
                if len(items) > 8:
                    answer += f"\n- ...and {len(items) - 8} more (see Validation)."
                if inc:
                    months = sorted({fmt_period(i['period']) for i in inc})
                    answer += (f"\n\n{len(inc)} monthly metric value(s) are INCOMPLETE because inputs are missing "
                               f"({', '.join(months[:4])}). They are shown as blanks, never estimated.")
        elif any(w in q for w in ["highest", "best", "peak", "max", "top", "lowest", "worst", "min"]):
            metric = self._metric(q)
            order = "asc" if any(w in q for w in ["lowest", "worst", "min"]) else "desc"
            r = tool("rank_months", metric=metric, order=order, top=3)
            if not r["top"]:
                answer = f"No complete monthly values are available for {r['name']}."
            else:
                first = r["top"][0]
                word = "lowest" if order == "asc" else "highest"
                answer = (f"The {word} {r['name']} month in the T-12 window was **{first['label']}** at "
                          f"**{first['display']}**.\n\nNext: " +
                          ", ".join(f"{t['label']} ({t['display']})" for t in r["top"][1:]) +
                          "\n\nRanked directly from engine month values.")
                if r["excluded_incomplete_months"]:
                    answer += f" Months excluded as incomplete: {', '.join(map(fmt_period, r['excluded_incomplete_months']))}."
        elif any(w in q for w in ["calculat", "formula", "how is", "how was", "show me", "derive", "trace"]):
            metric = self._metric(q, "ebitda")
            r = tool("explain_calculation", metric=metric, period=period)
            inputs = "\n".join(f"- {i['name']} ({fmt_period(i['period']) if i['period'] not in ('T12',) else 'T-12'}): {i['display']}"
                               for i in r["inputs"])
            src = ", ".join(r["source_documents"]) or "reviewer entries"
            pages = f", pages {', '.join(map(str, r['source_pages']))}" if r["source_pages"] else ""
            conf = f" Lowest extraction confidence among source values: {r['min_extraction_confidence']:.0%}." \
                if r.get("min_extraction_confidence") is not None else ""
            head = (f"**{r['name']} ({'T-12' if period == 'T12' else fmt_period(period)}) = {r['display']}** "
                    f"- status {r['status']}.\n\n")
            d = r.get("definition")
            if d:
                terms = "\n".join(f"- T-12 {i['name']}: {i['display']}" for i in d["on_t12_totals"])
                body = (f"Definition `{d['formula_id']}`: `{d['expression']}`, evaluated for every month and "
                        f"summed with `{r['formula_id']}`.\n\nOn T-12 totals:\n{terms}\n\n"
                        f"Cross-foot check (formula on totals = sum of months): "
                        f"{'passed' if d['crossfoot_passed'] else 'FAILED'}.")
            else:
                body = f"Formula `{r['formula_id']}`: `{r['formula']}`\n\nInputs:\n{inputs}"
            answer = (head + body + f"\n\nSource: {src}{pages}.{conf} "
                      "Open the Audit Trail on this metric for cell-level lineage.")
        elif "expense" in q or "cost" in q:
            r = tool("expense_changes")
            rows = sorted([c for c in r["categories"] if c["first3_to_last3_change"] is not None],
                          key=lambda c: c["first3_to_last3_change"], reverse=True)
            lines = [f"- {c['name']}: {fmt_pct(c['first3_to_last3_change'], True)} (avg {fmt_currency(c['first3_avg'])}"
                     f" -> {fmt_currency(c['last3_avg'])} per month)" for c in rows[:5]]
            answer = ("Expense change, first three vs last three months of the T-12 window:\n" + "\n".join(lines) +
                      f"\n\n**{rows[0]['name']}** increased the most." if rows else "Expense data is incomplete.")
        elif "why" in q or "change" in q or "driver" in q or "margin" in q:
            r = tool("margin_trend")
            e = tool("expense_changes")
            em = r["ebitda_margin"]
            li = e.get("largest_increase")
            if em["first3"] is None or em["last3"] is None:
                answer = "EBITDA margin movement cannot be explained because inputs in the window are incomplete."
            else:
                answer = (f"EBITDA margin moved from **{fmt_pct(em['first3'])}** (first three months) to "
                          f"**{fmt_pct(em['last3'])}** (last three), a change of {em['change_pp'] * 100:+.1f} pp.\n\n"
                          f"- Average monthly revenue: {fmt_pct(r['revenue_shift'], True)}\n"
                          f"- Average monthly operating expenses: {fmt_pct(r['operating_expenses_shift'], True)}\n"
                          f"- Average monthly gross profit: {fmt_pct(r['gross_profit_shift'], True)}\n")
                if li:
                    answer += f"- Fastest-growing cost line: {li['name']} ({fmt_pct(li['first3_to_last3_change'], True)})\n"
                answer += "\nRevenue growing faster than operating expenses expands the margin; the reverse compresses it."
        elif any(w in q for w in ["summary", "summarize", "overview", "management", "brief"]):
            facts = build_facts(ws)
            calls.append({"tool": "get_kpis+margin_trend+expense_changes+review_items", "args": {}, "result": facts})
            answer = self.narrate(facts)
        else:
            metric = self._metric(q, "")
            if metric:
                r = tool("get_metric", metric=metric, period=period)
                answer = (f"**{r['name']} ({'T-12' if period == 'T12' else fmt_period(period)}): {r['display']}** - "
                          f"status {r['status']}, formula `{(r.get('formula') or {}).get('expression', 'source value')}`.")
            else:
                r = tool("get_kpis")
                lines = [f"- {v['name']}: {v['display']}" for v in r["metrics"].values()]
                answer = ("Here are the verified T-12 KPIs:\n" + "\n".join(lines) +
                          "\n\nTry: *What was our highest revenue month?*, *Why did EBITDA change?*, "
                          "*Show me the calculation for EBITDA*, *Which numbers require review?*")
        return {"answer": answer, "tool_calls": calls}


# --------------------------------------------------------------------------- #
# Groq provider (live)
# --------------------------------------------------------------------------- #
class GroqProvider(LLMProvider):
    """Live LLM via the official ``groq`` SDK (OpenAI-compatible chat completions)."""

    name = "Groq"
    live = True

    def __init__(self) -> None:
        from groq import Groq

        self.client = Groq()  # reads GROQ_API_KEY
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def _chat(self, messages: list[dict], *, max_tokens: int = 2048, temperature: float = 0.1, **kwargs):
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            **kwargs,
        )
        return resp.choices[0].message

    def suggest_mappings(self, labels: list[str]) -> list[dict]:
        if not labels:
            return []
        taxonomy = [{"key": c.key, "name": c.name, "kind": c.kind, "examples": c.synonyms[:5]}
                    for c in CATEGORIES if c.key != "excluded"]
        system = (
            "You classify financial statement line-item labels into a fixed taxonomy. Use only the taxonomy "
            "keys provided. Use null when a label is ambiguous or does not clearly belong to one category. "
            'Respond with JSON only, shaped as {"mappings": [{"label": str, "category": str|null, '
            '"confidence": number between 0 and 1, "rationale": str}]} with one entry per input label.'
        )
        try:
            msg = self._chat(
                [{"role": "system", "content": system},
                 {"role": "user", "content": f"TAXONOMY:\n{json.dumps(taxonomy)}\n\nLABELS:\n{json.dumps(labels)}"}],
                max_tokens=2000, temperature=0, response_format={"type": "json_object"},
            )
            data = json.loads(msg.content or "{}")
            valid = {c.key for c in CATEGORIES}
            out = []
            for m in data.get("mappings", []):
                if not isinstance(m, dict) or m.get("label") not in labels:
                    continue
                if m.get("category") is not None and m.get("category") not in valid:
                    continue  # never accept an invented category
                try:
                    m["confidence"] = max(0.0, min(1.0, float(m.get("confidence", 0))))
                except (TypeError, ValueError):
                    m["confidence"] = 0.0
                out.append(m)
            return out
        except Exception as exc:
            log.warning("AI mapping suggestion failed: %s", exc)
            return []

    def classify_document(self, filename: str, sample: str) -> dict:
        try:
            msg = self._chat(
                [{"role": "system", "content": "Classify the financial document in one short phrase "
                  "(e.g. 'Monthly income statement (P&L)'). Reply with the phrase only."},
                 {"role": "user", "content": f"Filename: {filename}\n\nExcerpt:\n{sample[:3000]}"}],
                max_tokens=60, temperature=0,
            )
            text = (msg.content or "").strip().strip('"')
            if not text:
                raise ValueError("empty classification")
            return {"document_type": text[:120], "method": f"LLM ({self.model} via Groq)", "confidence": None}
        except Exception as exc:
            log.warning("AI classification failed: %s", exc)
            return super().classify_document(filename, sample)

    def narrate(self, facts: dict) -> str:
        msg = self._chat(
            [{"role": "system", "content": NARRATIVE_SYSTEM},
             {"role": "user", "content": "VERIFIED_FACTS:\n" + json.dumps(facts, default=str)}],
            max_tokens=700, temperature=0.2,
        )
        return (msg.content or "").strip()

    def assistant(self, ws, question: str, history: list[dict]) -> dict:
        tools = [{
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": {"type": "object", "properties": spec["params"]},
            },
        } for name, spec in ft.TOOLS.items()]
        messages: list[dict] = [{"role": "system", "content": ASSISTANT_SYSTEM}]
        messages += [{"role": h["role"], "content": h["content"]} for h in history[-8:]
                     if h.get("role") in ("user", "assistant") and h.get("content")]
        messages.append({"role": "user", "content": question})
        calls: list[dict] = []
        for _ in range(6):
            msg = self._chat(messages, tools=tools, tool_choice="auto", max_tokens=1500)
            if not msg.tool_calls:
                return {"answer": (msg.content or "").strip(), "tool_calls": calls}
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                               for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be an object")
                    out = ft.call_tool(ws, tc.function.name, args)
                except (json.JSONDecodeError, ValueError) as exc:
                    args, out = {}, {"error": f"Invalid tool arguments: {exc}"}
                calls.append({"tool": tc.function.name, "args": args, "result": out})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out, default=str)})
        return {"answer": "I could not complete the analysis within the tool-call limit.", "tool_calls": calls}


# --------------------------------------------------------------------------- #
def build_facts(ws) -> dict:
    return {
        "kpis": ft.get_kpis(ws),
        "margins": ft.margin_trend(ws),
        "expenses": ft.expense_changes(ws),
        "revenue_peak": ft.rank_months(ws, "revenue", "desc", 1),
        "review": ft.review_items(ws),
    }


_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        if os.getenv("GROQ_API_KEY") and os.getenv("FIW_DISABLE_LLM") != "1":
            try:
                _provider = GroqProvider()
            except Exception as exc:  # pragma: no cover
                log.warning("Falling back to mock provider: %s", exc)
                _provider = MockProvider()
        else:
            _provider = MockProvider()
    return _provider


def provider_info() -> dict:
    p = get_provider()
    return {"name": p.name, "model": p.model, "live": p.live}


def guarded(generate: Callable[[], str], allowed_source: Any, fallback: Callable[[], str]) -> dict:
    """Run a text generator, then verify every numeric claim against engine values."""
    allowed = ft.collect_numbers(allowed_source)
    note = None
    try:
        text = generate()
    except Exception as exc:
        log.warning("AI generation failed, using deterministic template: %s", exc)
        text, note = fallback(), "AI provider unavailable - deterministic template used."
    check = verify_numeric_claims(text, allowed)
    if not check["passed"]:
        note = (f"AI draft contained {len(check['unverified'])} figure(s) not traceable to the engine "
                f"({', '.join(check['unverified'][:3])}); replaced with the deterministic template.")
        text = fallback()
        check = verify_numeric_claims(text, allowed)
    return {"text": text, "numeric_check": check, "note": note}
