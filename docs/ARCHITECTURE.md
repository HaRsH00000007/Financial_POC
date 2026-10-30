# Architecture: Finance Intelligence Workbench

## 1. Principle

In high-stakes finance, a *statistically likely* number is not an acceptable number. The platform therefore splits
responsibilities into three layers, and the boundary between them is enforced in code, not just by convention:

```
USER
  ↓
AI / ORCHESTRATION LAYER          (probabilistic: understands, classifies, explains, coordinates)
  ↓
DATA EXTRACTION + NORMALIZATION   (rules first; AI only assists; humans confirm)
  ↓
DETERMINISTIC FINANCIAL ENGINE    (the only place arithmetic happens)
  ↓
AUDIT / TRACEABILITY LAYER        (source refs, lineage, hash-chained events)
  ↓
AI-GENERATED INSIGHTS / REPORTING (language over verified outputs, numerically guarded)
```

| Probabilistic AI | Deterministic engine | Trust / audit |
|---|---|---|
| Document classification | Arithmetic | Source references (doc, page, sheet!cell, raw token) |
| Label → taxonomy *suggestions* | Formula evaluation | Formula lineage trees |
| Narrative commentary | Category aggregation | Calculation history (every result stores formula + inputs) |
| Natural-language Q&A (tool calling) | T-12 totals, margins, growth | Immutable, hash-chained audit events |
| Agent orchestration | Reconciliation, cross-foot | Human review with mandatory justification |
| | Validation rules | Data provenance (document SHA-256) |

## 2. How the separation is enforced

1. **Arithmetic exists in one module.** `backend/app/calculations/` (expression evaluator, formula registry, engine).
   API routes, agents and the AI layer call it; none of them compute. The frontend only formats numbers (`src/lib/format.ts`).
2. **Formulas are data.** Each formula has an ID, expression and inputs (`formulas.py`). Expressions are parsed with
   Python's `ast` and only names, numbers, `+ - * /` and parentheses are allowed, so a formula cannot execute code.
   Evaluation uses `decimal.Decimal` (exact: `0.1 + 0.2 == 0.3`).
3. **Missing inputs propagate.** If any input is `None`, the result is `None` with status `INCOMPLETE` and the missing names
   are recorded. Division by zero is `UNDEFINED`. T-12 totals require all 12 months and are never extrapolated.
4. **The LLM receives verified outputs.**
   * *Commentary*: the Synthesis Agent gets a facts bundle built by deterministic tools (`finance_tools.py`).
   * *Assistant*: the LLM may only call tools (`get_kpis`, `get_metric`, `rank_months`, `explain_calculation`,
     `expense_changes`, `margin_trend`, `review_items`, ...), which read the verified model or run engine formulas.
     The flow is LLM → tool → engine → result → explanation.
5. **Numeric-claim guard.** Every number in AI text is parsed (`$4.21M`, `21.1%`, `2.9 pp`, ...) and must match an engine
   value at its stated precision (`services/formatting.py::verify_numeric_claims`). If a draft fails, it is replaced by a
   deterministic template, and the UI shows "N/N figures verified against engine".
6. **Rules before AI in normalization.** Exact synonym → fuzzy match (WARNING) → AI suggestion (WARNING, only for rows
   the rules could not map) → unmapped (REVIEW REQUIRED). A reviewer override always wins and is audited.

## 3. Data model (`backend/app/models/domain.py`)

`Document` → `RawLineItem` (label, values per period, `SourceReference` per value) → `Mapping` (to a `NormalizedCategory`)
→ `FinancialValue` (category × period, component row ids, source) → `Formula` → `CalculationResult`
(formula ID, expression, substituted expression, inputs, result, status, missing inputs, engine version) →
`AuditEvent` (seq, actor, agent, type, details, `prev_hash`, `hash`). Validation produces `ValidationCheck` records
(`VALID` / `WARNING` / `REVIEW_REQUIRED`).

## 4. Formula registry

| ID | Metric | Expression |
|---|---|---|
| AGG_001 | category total | `row_1 + row_2 + …` (source rows mapped to one category) |
| OPEX_001 | operating_expenses | `payroll + rent + sales_marketing + technology + general_admin + other_opex` (components reported in the source) |
| GP_001 | gross_profit | `revenue - cogs` |
| EBITDA_001 | ebitda | `gross_profit - operating_expenses` |
| NI_001 | net_income | `ebitda - depreciation - interest - taxes` |
| GM_001 / EBITDAM_001 / NM_001 | margins | `x / revenue` (on T-12 totals, never averaged) |
| T12_001 | T-12 total | `m01 + … + m12` |
| GROWTH_001 | growth | `(current - prior) / prior` |
| DIFF_001 | change | `current - prior` (margin movement in pp) |
| REC_001 | reconciliation | `reported - computed` |
| AVG3_001 | 3-month average | `(a + b + c) / 3` |

The engine evaluates per-period formulas in topological order (derived from the expressions). It then computes T-12 and
prior-T-12 totals, ratios on totals, YoY growth, reconciliations against **printed** subtotals (which are never used as
inputs), and cross-foot checks (formula applied to T-12 totals = sum of monthly results).

## 5. Agent orchestration

`agents/pipeline.py` uses a Coordinator–Specialist pattern:

| Agent | Layer | Does |
|---|---|---|
| Coordinator | orchestration | Plans the workflow; pauses for human review before calculation |
| Ingestion | probabilistic + rules | Classifies the document (LLM if configured) and extracts tables with provenance |
| Normalization | probabilistic + rules | Maps labels; AI suggestions only for rows the rules could not map |
| Validation | deterministic | Coverage, gaps, missing values, duplicates, outliers, sign convention, unit scale, reconciliation |
| Calculation | deterministic | Runs the engine; this code path contains no LLM call |
| Synthesis | probabilistic | Commentary over verified facts, numeric-guarded |

Every step appends an `AuditEvent`. The chain is verifiable (`GET /api/workspaces/{id}/audit` returns `integrity`), and
tampering with any past event breaks it (tested).

## 6. Lineage

`audit/lineage.py` builds a tree for any `(metric, period)`, where period is a month, `T12`, `T12_PRIOR` or `YOY`:
result → formula (with substituted values) → input nodes → source category → raw rows → `SourceReference`
(document, page / sheet!cell, raw token, extraction method, confidence, mapping method). Aggregates gather every
underlying source cell. The UI's Audit Trail drawer renders the chain **Source document → Extracted value → Normalized
category → Formula → Calculated result**, and you can drill into any input.

## 7. LLM provider abstraction

`services/llm.py` defines `LLMProvider` with two implementations:

* `GroqProvider`: official `groq` SDK (OpenAI-compatible chat completions), key from `GROQ_API_KEY`, model from
  `GROQ_MODEL` (default `llama-3.3-70b-versatile`). It uses JSON mode for mapping suggestions (only known taxonomy keys
  are accepted) and a function-calling loop for the assistant. Malformed tool arguments are returned to the model as
  tool errors and never executed.
* `MockProvider`: deterministic, offline, and labelled "Mock AI (offline)" in the UI.

Any provider error falls back to the offline path, and the response carries a note that says so. If a live answer or commentary contains a figure that isn't traceable to engine values, it is replaced with the deterministic version, and the UI says why.

## 8. API surface

```
GET  /api/health | /api/meta | /api/samples/{name}
POST /api/workspaces/demo?fmt=pdf|xlsx|csv        POST /api/workspaces/upload (multipart)
GET  /api/workspaces/{id}                          PUT  /api/workspaces/{id}/mappings
POST /api/workspaces/{id}/resolutions              DELETE /api/workspaces/{id}/resolutions/{rid}
POST /api/workspaces/{id}/calculate                GET  /api/workspaces/{id}/model
GET  /api/workspaces/{id}/lineage?metric=&period=  GET  /api/workspaces/{id}/audit
POST /api/workspaces/{id}/commentary               POST /api/workspaces/{id}/assistant
GET  /api/evaluation/framework   POST /api/evaluation/summary   POST /api/evaluation/report
```

## 9. Evaluation module

Fifteen dimensions (accuracy, deterministic calculation, auditability, explainability, lineage, AI capabilities, agentic
workflow, automation, integration, security, governance, human-in-the-loop, regulatory readiness, reporting, UX). Each
dimension has guiding questions and suggested tests. The evaluator records evidence, vendor claims, test results,
documentation references and limitations, then assigns an assessment. The only computation is a transparent weighted
index (`Σ w·s / Σ w·4` over *assessed* dimensions, evaluated by the same deterministic evaluator). It is explicitly **not**
an industry benchmark. Vendor claims without a supporting test are counted and surfaced.

## 10. Production path (beyond the POC)

Persistent store (Postgres) with an append-only audit table and signed checkpoints; OCR / layout models for scanned
documents with the same provenance contract; a broader chart of accounts, XBRL/LEI tagging and a balance sheet /
cash-flow engine; maker-checker approvals and RBAC; model risk documentation (SR 11-7) for the AI components; and an
eval set for extraction and mapping accuracy.
