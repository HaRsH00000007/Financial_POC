"""In-memory T-12 workspace (one per processed document).

This is a POC store: state lives in process memory. The shape is what a
persistent implementation would store per engagement.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Optional

from app.audit.log import AuditLog
from app.calculations import engine
from app.calculations.formulas import OPEX_COMPONENTS
from app.extraction.extractors import ExtractionResult
from app.models.domain import (
    CalcStatus,
    Document,
    FinancialValue,
    Mapping,
    RawLineItem,
    SourceReference,
    Status,
    ValidationCheck,
)
from app.normalization.taxonomy import BY_KEY

EXPENSE_CATEGORIES = {"cogs", *OPEX_COMPONENTS, "depreciation", "interest", "taxes"}
REQUIRED_CATEGORIES = ["revenue", "cogs", "depreciation", "interest", "taxes"]


@dataclass
class Resolution:
    id: str
    type: str                      # "value" | "category_zero"
    note: str
    row_id: str | None = None
    period: str | None = None
    value: float | None = None
    category: str | None = None


@dataclass
class Workspace:
    id: str
    document: Document
    extraction: ExtractionResult
    rows: dict[str, RawLineItem]
    mappings: dict[str, Mapping] = field(default_factory=dict)
    resolutions: list[Resolution] = field(default_factory=list)
    checks: list[ValidationCheck] = field(default_factory=list)
    model: dict | None = None
    stage: str = "extracted"
    audit: AuditLog = field(default_factory=AuditLog)
    agent_runs: list[dict] = field(default_factory=list)
    classification: dict = field(default_factory=dict)
    commentary: dict | None = None
    sign_flips: list[str] = field(default_factory=list)
    stale: bool = False

    # ------------------------------------------------------------------ #
    # Deterministic input assembly (mapping -> category values)
    # ------------------------------------------------------------------ #
    def effective_row_values(self, row: RawLineItem) -> tuple[dict[str, Optional[float]], dict[str, SourceReference]]:
        """Row values after unit scaling, sign-convention and reviewer resolutions."""
        scale = self.extraction.scale
        values = {p: (None if v is None else v * scale) for p, v in row.values.items()}
        sources = dict(row.sources)
        if row.id in self.sign_flips:
            values = {p: (None if v is None else -v) for p, v in values.items()}
        for r in self.resolutions:
            if r.type == "value" and r.row_id == row.id and r.period:
                values[r.period] = r.value
                sources[r.period] = SourceReference(
                    document_id="reviewer", document_name="Reviewer entry", row_label=row.label,
                    raw_text=r.note, extraction_method="manual-entry (audited)", confidence=1.0)
        return values, sources

    def category_rows(self) -> dict[str, list[RawLineItem]]:
        out: dict[str, list[RawLineItem]] = {}
        for rid, m in self.mappings.items():
            if m.category and m.category != "excluded":
                out.setdefault(m.category, []).append(self.rows[rid])
        return out

    def category_values(self) -> dict[str, dict[str, FinancialValue]]:
        periods = self.extraction.periods
        result: dict[str, dict[str, FinancialValue]] = {}
        for cat, rows in self.category_rows().items():
            per: dict[str, FinancialValue] = {}
            eff = [self.effective_row_values(r) for r in rows]
            for p in periods:
                agg = engine.aggregate_rows([vals.get(p) for vals, _ in eff], metric=cat, period=p)
                src = eff[0][1].get(p) if len(rows) == 1 else None
                per[p] = FinancialValue(metric=cat, period=p, value=agg.result, source=src,
                                        component_rows=[r.id for r in rows], status=agg.status)
            result[cat] = per
        for r in self.resolutions:
            if r.type == "category_zero" and r.category and r.category not in result:
                src = SourceReference(document_id="reviewer", document_name="Reviewer attestation",
                                      row_label=BY_KEY[r.category].name, raw_text=r.note,
                                      extraction_method="reviewer-attested zero (audited)", confidence=1.0)
                result[r.category] = {p: FinancialValue(metric=r.category, period=p, value=0.0, source=src)
                                      for p in periods}
        return result

    def engine_inputs(self) -> tuple[dict, dict]:
        cv = self.category_values()
        inputs, reported = {}, {}
        for cat, per in cv.items():
            kind = BY_KEY[cat].kind
            series = {p: fv.value for p, fv in per.items()}
            if kind == "input":
                inputs[cat] = series
            elif kind == "reported_subtotal":
                reported[cat] = series
        return inputs, reported


class WorkspaceStore:
    def __init__(self) -> None:
        self._items: dict[str, Workspace] = {}
        self._lock = threading.Lock()

    def create(self, document: Document, extraction: ExtractionResult) -> Workspace:
        ws = Workspace(id=uuid.uuid4().hex[:12], document=document, extraction=extraction,
                       rows={r.id: r for r in extraction.rows})
        with self._lock:
            self._items[ws.id] = ws
        return ws

    def get(self, ws_id: str) -> Workspace | None:
        return self._items.get(ws_id)

    def list(self) -> list[Workspace]:
        return list(self._items.values())


STORE = WorkspaceStore()


# ---------------------------------------------------------------------- #
# Validation rules (deterministic)
# ---------------------------------------------------------------------- #
def detect_sign_flips(ws: Workspace) -> list[str]:
    flips = []
    for rid, m in ws.mappings.items():
        if m.category in EXPENSE_CATEGORIES:
            vals = [v for v in ws.rows[rid].values.values() if v is not None]
            if vals and all(v <= 0 for v in vals) and any(v < 0 for v in vals):
                flips.append(rid)
    return flips


def run_validation(ws: Workspace) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    periods = ws.extraction.periods
    n = 0

    def add(check: str, status: Status, title: str, detail: str, **kw: Any) -> None:
        nonlocal n
        n += 1
        checks.append(ValidationCheck(id=f"v{n:03d}", check=check, status=status, title=title, detail=detail, **kw))

    # 1. Period coverage and date consistency
    if not periods:
        add("periods", Status.REVIEW_REQUIRED, "No monthly periods detected",
            "The extractor did not find a header row with monthly periods.")
    else:
        years_months = [(int(p[:4]), int(p[5:])) for p in periods]
        idx = [y * 12 + m for y, m in years_months]
        gaps = [(periods[i], periods[i + 1]) for i in range(len(idx) - 1) if idx[i + 1] - idx[i] != 1]
        if gaps:
            add("date_consistency", Status.REVIEW_REQUIRED, "Non-contiguous periods",
                "Gaps between: " + ", ".join(f"{a} -> {b}" for a, b in gaps))
        else:
            add("date_consistency", Status.VALID, "Periods are contiguous",
                f"{len(periods)} consecutive months from {periods[0]} to {periods[-1]}.")
        if len(periods) < 12:
            add("t12_coverage", Status.REVIEW_REQUIRED, "Fewer than 12 months",
                f"Only {len(periods)} months available; a full T-12 cannot be computed.")
        else:
            prior = "Prior-year window available for YoY comparison." if len(periods) >= 24 else \
                "No complete prior-year window - YoY growth will be reported as not computable."
            add("t12_coverage", Status.VALID, "T-12 window available",
                f"Trailing window {periods[-12]} to {periods[-1]}. {prior}")

    # 2. Unit scale
    if ws.extraction.scale != 1:
        add("units", Status.WARNING, f"Values scaled x{ws.extraction.scale:,.0f}",
            "The document states its figures in thousands/millions; values were multiplied deterministically.")

    # 3. Mapping status
    for rid, m in ws.mappings.items():
        if m.category is None:
            add("unmapped", Status.REVIEW_REQUIRED, f'Unmapped row: "{m.raw_label}"',
                "Map this row to a category or exclude it. It is not used in any calculation until then.",
                row_id=rid, resolvable=True)
        elif m.method in ("fuzzy_match", "ai_suggested"):
            add("mapping_confidence", Status.WARNING, f'Mapping needs confirmation: "{m.raw_label}"',
                f"{m.method.replace('_', ' ')} -> {BY_KEY[m.category].name} ({m.confidence:.0%}). {m.rationale}",
                row_id=rid, category=m.category, resolvable=True)

    # 4. Required categories
    cat_rows = ws.category_rows()
    attested = {r.category for r in ws.resolutions if r.type == "category_zero"}
    for cat in REQUIRED_CATEGORIES:
        if cat not in cat_rows:
            if cat in attested:
                add("required_category", Status.WARNING, f"{BY_KEY[cat].name} attested as zero",
                    "Not present in the source; a reviewer attested the value is zero for all periods.",
                    category=cat)
            else:
                add("required_category", Status.REVIEW_REQUIRED, f"{BY_KEY[cat].name} not found",
                    "Not present in the source. Map a row to it, or attest that it is zero. "
                    "Dependent metrics stay INCOMPLETE until resolved.", category=cat, resolvable=True)
    if not any(c in cat_rows for c in OPEX_COMPONENTS) and "operating_expenses_reported" not in cat_rows:
        add("required_category", Status.REVIEW_REQUIRED, "No operating expenses found",
            "Neither expense components nor a reported operating-expense total were mapped.")

    # 5. Missing values (never imputed)
    window = set(periods[-24:])
    for rid, m in ws.mappings.items():
        if not m.category or m.category == "excluded":
            continue
        vals, _ = ws.effective_row_values(ws.rows[rid])
        kind = BY_KEY[m.category].kind
        for p in periods:
            if vals.get(p) is None and p in window:
                status = Status.REVIEW_REQUIRED if kind == "input" else Status.WARNING
                add("missing_value", status, f'Missing value: "{m.raw_label}" - {p}',
                    "No value in the source for this period. It will NOT be estimated; enter a reviewed value "
                    "or leave it missing (dependent metrics become INCOMPLETE).",
                    row_id=rid, period=p, category=m.category, resolvable=kind == "input")

    # 6. Duplicates (possible double counting)
    for cat, rows in cat_rows.items():
        seen: dict[tuple, str] = {}
        for r in rows:
            sig = tuple(r.values.get(p) for p in periods)
            if sig in seen and any(v is not None for v in sig):
                add("duplicate", Status.WARNING, f"Possible duplicate in {BY_KEY[cat].name}",
                    f'"{r.label}" has identical values to "{ws.rows[seen[sig]].label}" in every period. '
                    "Both are currently summed - exclude one if this is double counting.",
                    row_id=r.id, category=cat, resolvable=True)
            seen.setdefault(sig, r.id)

    # 7. Sign convention
    for rid in ws.sign_flips:
        add("sign_convention", Status.WARNING, f'Sign convention normalized: "{ws.rows[rid].label}"',
            "Expense presented as negative numbers in the source; signs flipped so expenses are positive "
            "for formula evaluation.", row_id=rid)

    # 8. Suspicious values (robust median rule)
    for rid, m in ws.mappings.items():
        if not m.category or BY_KEY[m.category].kind != "input":
            continue
        vals, _ = ws.effective_row_values(ws.rows[rid])
        known = [abs(v) for v in vals.values() if v is not None]
        if len(known) < 6:
            continue
        med = median(known)
        for p, v in vals.items():
            if v is None:
                continue
            if m.category == "revenue" and v < 0:
                add("suspicious", Status.WARNING, f"Negative revenue in {p}", f'"{m.raw_label}" = {v:,.2f}',
                    row_id=rid, period=p)
            elif med > 0 and abs(v) > 3 * med:
                add("suspicious", Status.WARNING, f'Outlier: "{m.raw_label}" - {p}',
                    f"{v:,.0f} is {abs(v) / med:.1f}x the row median ({med:,.0f}). Confirm it is not an "
                    "extraction error (e.g. a misplaced digit) or a one-off item.", row_id=rid, period=p)

    # 9. Extraction issues
    for issue in ws.extraction.issues:
        add("extraction", Status.REVIEW_REQUIRED, f"Extraction issue on page {issue.get('page')}",
            f"{issue.get('label')}: {issue.get('detail')}")
    for r in ws.rows.values():
        for note in r.notes:
            if "Conflicting" in note or "no cached value" in note:
                add("extraction", Status.REVIEW_REQUIRED, f'Extraction issue: "{r.label}"', note, row_id=r.id)

    # 10. Reconciliation of source subtotals (deterministic engine)
    inputs, reported = ws.engine_inputs()
    if reported and inputs:
        preview = engine.build_model(periods, inputs, reported)
        by_metric: dict[str, list[dict]] = {}
        for rec in preview["reconciliations"]:
            by_metric.setdefault(rec["metric"], []).append(rec)
        for metric, recs in by_metric.items():
            bad = [r for r in recs if not r["matches"]]
            name = BY_KEY[recs[0]["reported_category"]].name
            if bad:
                periods_txt = ", ".join(r["period"] for r in bad[:6]) + (" ..." if len(bad) > 6 else "")
                add("reconciliation", Status.WARNING,
                    f"{name} does not reconcile in {len(bad)} of {len(recs)} periods",
                    f"The engine's recomputed value differs from the subtotal printed in the source ({periods_txt}). "
                    "Engine values are used. A consistent variance usually means a source row is unmapped or "
                    "excluded; an isolated one suggests an error in the source document.",
                    category=recs[0]["reported_category"],
                    evidence=[{"period": r["period"], "reported": r["reported"], "computed": r["computed"],
                               "variance": r["variance"]} for r in bad])
            else:
                add("reconciliation", Status.VALID, f"{name} reconciles",
                    f"Recomputed value matches the source subtotal in all {len(recs)} periods compared.",
                    category=recs[0]["reported_category"])

    # 11. Reviewer interventions are always visible
    for r in ws.resolutions:
        if r.type == "value" and r.row_id in ws.rows:
            add("manual_entry", Status.WARNING, f'Reviewer-entered value: "{ws.rows[r.row_id].label}" - {r.period}',
                f"{r.value:,.2f} entered manually. Justification: {r.note}", row_id=r.row_id, period=r.period,
                evidence=[{"resolution_id": r.id}])

    # mark resolved checks
    resolved_cells = {(r.row_id, r.period) for r in ws.resolutions if r.type == "value"}
    for c in checks:
        if c.check == "missing_value" and (c.row_id, c.period) in resolved_cells:
            c.resolved = True
    return checks


def summarize_checks(checks: list[ValidationCheck]) -> dict:
    counts = {s.value: 0 for s in Status}
    for c in checks:
        counts[c.status.value] += 1
    overall = Status.VALID
    if counts["REVIEW_REQUIRED"]:
        overall = Status.REVIEW_REQUIRED
    elif counts["WARNING"]:
        overall = Status.WARNING
    return {"counts": counts, "overall": overall.value, "total": len(checks)}


def incomplete_metrics(model: dict) -> list[dict]:
    out = []
    for metric, per in model.get("per_period", {}).items():
        for p, r in per.items():
            if p in model["window"] and r["status"] != CalcStatus.DETERMINISTIC.value:
                out.append({"metric": metric, "period": p, "status": r["status"], "missing": r["missing_inputs"]})
    return out
