"""Annual-report workspace: several reports of one company, one multi-year model.

Each annual report prints two fiscal years, so consecutive reports overlap (the
FY2025 figures appear in both the 2025 and the 2026 report). For every category
and year the engine input comes from the most recent report that prints it -
companies restate comparatives - and every difference against an earlier report
is recorded as a restatement for review. Values are never summed across reports.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from app.annual import engine as aengine
from app.annual.rag import BM25Index
from app.annual.statements import STATEMENTS, StatementLocation
from app.annual.taxonomy import BY_KEY
from app.audit.log import AuditLog
from app.calculations import engine
from app.models.domain import CalcStatus, Document, FinancialValue, Mapping, RawLineItem, SourceReference, Status, ValidationCheck
from app.services.workspace import Resolution

REQUIRED = ["revenue", "other_income", "materials_cost", "employee_costs", "finance_costs", "depreciation",
            "other_expenses", "current_tax", "deferred_tax", "share_capital", "other_equity", "borrowings_nc",
            "borrowings_c", "cash_equivalents", "cfo", "cfi", "cff", "opening_cash"]


@dataclass
class ReportFile:
    document: Document
    pages: list[str]
    fiscal_years: list[str]
    unit: str
    statements: dict[str, StatementLocation]
    text_engine: str


@dataclass
class RowMeta:
    document_id: str
    statement: str
    section: str
    note_ref: Optional[str]


@dataclass
class ExtractionInfo:
    periods: list[str]
    scale: float = 1.0
    log: list[str] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    entity_name: Optional[str] = None


@dataclass
class AnnualWorkspace:
    id: str
    reports: list[ReportFile]
    rows: dict[str, RawLineItem]
    row_meta: dict[str, RowMeta]
    index: BM25Index
    extraction: ExtractionInfo
    currency: str = "INR"
    unit: str = "crore"
    kind: str = "annual"
    mappings: dict[str, Mapping] = field(default_factory=dict)
    resolutions: list[Resolution] = field(default_factory=list)
    checks: list[ValidationCheck] = field(default_factory=list)
    model: dict | None = None
    stage: str = "extracted"
    audit: AuditLog = field(default_factory=AuditLog)
    agent_runs: list[dict] = field(default_factory=list)
    classification: dict = field(default_factory=dict)
    commentary: dict | None = None
    exposure: list[dict] = field(default_factory=list)
    external: list[dict] = field(default_factory=list)
    sign_flips: list[str] = field(default_factory=list)
    stale: bool = False

    # Compatibility with the shared HTTP layer / lineage helpers.
    @property
    def document(self) -> Document:
        return self.reports[-1].document

    @property
    def documents(self) -> dict[str, ReportFile]:
        return {r.document.id: r for r in self.reports}

    def report_rank(self, document_id: str) -> int:
        """Higher = more recent report (by latest fiscal year printed)."""
        r = self.documents[document_id]
        return int(max(r.fiscal_years)[2:]) if r.fiscal_years else 0

    def effective_row_values(self, row: RawLineItem) -> tuple[dict[str, Optional[float]], dict[str, SourceReference]]:
        values = dict(row.values)
        sources = dict(row.sources)
        for r in self.resolutions:
            if r.type == "value" and r.row_id == row.id and r.period:
                values[r.period] = r.value
                sources[r.period] = SourceReference(
                    document_id="reviewer", document_name="Reviewer entry", row_label=row.label, raw_text=r.note,
                    extraction_method="manual-entry (audited)", confidence=1.0)
        return values, sources

    def category_rows(self) -> dict[str, list[RawLineItem]]:
        out: dict[str, list[RawLineItem]] = {}
        for rid, m in self.mappings.items():
            if m.category and m.category != "excluded":
                out.setdefault(m.category, []).append(self.rows[rid])
        return out

    def _per_document(self) -> dict[str, dict[str, dict[str, tuple[Any, list[RawLineItem]]]]]:
        """category -> document -> period -> (aggregate result, rows)."""
        out: dict = {}
        for cat, rows in self.category_rows().items():
            by_doc: dict[str, list[RawLineItem]] = {}
            for r in rows:
                by_doc.setdefault(self.row_meta[r.id].document_id, []).append(r)
            for doc_id, drows in by_doc.items():
                eff = [self.effective_row_values(r)[0] for r in drows]
                for p in self.documents[doc_id].fiscal_years:
                    agg = engine.aggregate_rows([v.get(p) for v in eff], metric=cat, period=p)
                    out.setdefault(cat, {}).setdefault(doc_id, {})[p] = (agg, drows)
        return out

    def source_report(self, statement: str, period: str) -> Optional[str]:
        """The most recent report that prints this statement for this year."""
        docs = [r.document.id for r in self.reports if period in r.fiscal_years and statement in r.statements]
        return max(docs, key=self.report_rank) if docs else None

    def category_values(self) -> dict[str, dict[str, FinancialValue]]:
        """Per year, each statement is taken whole from one report (the latest that prints it).

        A category that report does not print for that year is "not printed" (no entry),
        which the engine treats differently from a printed-but-missing value.
        """
        result: dict[str, dict[str, FinancialValue]] = {}
        for cat, by_doc in self._per_document().items():
            per: dict[str, FinancialValue] = {}
            for p in self.extraction.periods:
                doc_id = self.source_report(BY_KEY[cat].statement, p)
                if doc_id is None or p not in by_doc.get(doc_id, {}):
                    continue
                agg, drows = by_doc[doc_id][p]
                src = self.effective_row_values(drows[0])[1].get(p) if len(drows) == 1 else None
                per[p] = FinancialValue(metric=cat, period=p, value=agg.result, currency=self.currency, source=src,
                                        component_rows=[r.id for r in drows], status=agg.status)
            result[cat] = per
        for r in self.resolutions:
            if r.type == "category_zero" and r.category and r.category not in result:
                src = SourceReference(document_id="reviewer", document_name="Reviewer attestation",
                                      row_label=BY_KEY[r.category].name, raw_text=r.note,
                                      extraction_method="reviewer-attested zero (audited)", confidence=1.0)
                result[r.category] = {p: FinancialValue(metric=r.category, period=p, value=0.0, source=src)
                                      for p in self.extraction.periods}
        return result

    def restatements(self) -> list[dict]:
        out = []
        for cat, by_doc in self._per_document().items():
            if BY_KEY[cat].kind == "memo":  # memo lines are not used by the engine
                continue
            for p in self.extraction.periods:
                docs = sorted([d for d in by_doc if p in by_doc[d] and by_doc[d][p][0].result is not None],
                              key=self.report_rank)
                if len(docs) < 2:
                    continue
                latest = docs[-1]
                lv = by_doc[latest][p][0].result
                for d in docs[:-1]:
                    ov = by_doc[d][p][0].result
                    if abs(ov - lv) > 0.5:
                        out.append({"category": cat, "name": BY_KEY[cat].name, "period": p,
                                    "original_document": self.documents[d].document.filename, "original": ov,
                                    "restated_document": self.documents[latest].document.filename, "restated": lv,
                                    "difference": round(lv - ov, 2)})
        return out

    def engine_inputs(self) -> tuple[dict, dict]:
        inputs, reported = {}, {}
        for cat, per in self.category_values().items():
            kind = BY_KEY[cat].kind
            series = {p: fv.value for p, fv in per.items()}
            if kind == "input":
                inputs[cat] = series
            elif kind == "reported_subtotal":
                reported[cat] = series
        return inputs, reported


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------- #
# Validation (deterministic)
# ---------------------------------------------------------------------- #
def run_validation(ws: AnnualWorkspace) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    n = 0

    def add(check: str, status: Status, title: str, detail: str, **kw: Any) -> None:
        nonlocal n
        n += 1
        checks.append(ValidationCheck(id=f"v{n:03d}", check=check, status=status, title=title, detail=detail, **kw))

    # 1. Statement location per report
    for rep in ws.reports:
        name = rep.document.filename
        for kind, label in STATEMENTS.items():
            loc = rep.statements.get(kind)
            if not loc:
                add("statement_location", Status.REVIEW_REQUIRED, f"{label} not found in {name}",
                    "Neither the structural markers nor retrieval located this statement.")
            elif loc.score < 1.0:
                add("statement_location", Status.WARNING if loc.score >= 0.8 else Status.REVIEW_REQUIRED,
                    f"{label} located with lower certainty in {name} (p.{loc.page})",
                    f"Method: {loc.method}. Scope: {loc.scope}. Candidates: {loc.candidates}. Confirm the page.")
            else:
                add("statement_location", Status.VALID, f"{label}: {name} p.{loc.page}",
                    f"{loc.method}; scope {loc.scope}; BM25 rank {loc.bm25_rank or '-'}; candidate pages {loc.candidates}.")

    # 2. Periods and units
    periods = ws.extraction.periods
    if not periods:
        add("periods", Status.REVIEW_REQUIRED, "No fiscal years detected", "No statement header with fiscal-year columns.")
    else:
        years = [int(p[2:]) for p in periods]
        gaps = [f"FY{a} -> FY{b}" for a, b in zip(years, years[1:]) if b - a != 1]
        if gaps:
            add("periods", Status.WARNING, "Non-contiguous fiscal years", "Gaps: " + ", ".join(gaps))
        else:
            add("periods", Status.VALID, f"{len(periods)} consecutive fiscal years",
                f"{periods[0]} to {periods[-1]} across {len(ws.reports)} report(s).")
    units = {r.unit for r in ws.reports}
    if len(units) > 1 or "unknown" in units:
        add("units", Status.REVIEW_REQUIRED, "Reporting units differ or are unknown",
            f"Units detected per report: {', '.join(f'{r.document.filename}: {r.unit}' for r in ws.reports)}.")
    else:
        add("units", Status.VALID, f"All figures in {ws.currency} {next(iter(units))}",
            "Unit read from each statement header; values are used as printed (no rescaling).")

    # 3. Mapping status
    for rid, m in ws.mappings.items():
        meta = ws.row_meta[rid]
        if m.category is None:
            add("unmapped", Status.REVIEW_REQUIRED, f'Unmapped row: "{m.raw_label}"',
                f"{STATEMENTS[meta.statement]} · {meta.section or 'no section'}. Map it or exclude it; it is not used "
                "until then.", row_id=rid, resolvable=True)
        elif m.method in ("fuzzy_match", "ai_suggested"):
            add("mapping_confidence", Status.WARNING, f'Mapping needs confirmation: "{m.raw_label}"',
                f"{m.method.replace('_', ' ')} -> {BY_KEY[m.category].name} ({m.confidence:.0%}). {m.rationale}",
                row_id=rid, category=m.category, resolvable=True)

    # 4. Required categories
    cat_rows = ws.category_rows()
    attested = {r.category for r in ws.resolutions if r.type == "category_zero"}
    for cat in REQUIRED:
        if cat in cat_rows:
            continue
        if cat in attested:
            add("required_category", Status.WARNING, f"{BY_KEY[cat].name} attested as zero",
                "Not present in the reports; a reviewer attested the value is zero.", category=cat)
        else:
            add("required_category", Status.REVIEW_REQUIRED, f"{BY_KEY[cat].name} not found",
                "Map a row to it or attest that it is zero. Dependent metrics stay INCOMPLETE until resolved.",
                category=cat, resolvable=True)

    # 5. Missing values (never imputed)
    for rid, m in ws.mappings.items():
        if not m.category or m.category == "excluded" or BY_KEY[m.category].kind == "memo":
            continue
        vals, _ = ws.effective_row_values(ws.rows[rid])
        for p in ws.documents[ws.row_meta[rid].document_id].fiscal_years:
            if vals.get(p) is None:
                add("missing_value", Status.REVIEW_REQUIRED, f'Missing value: "{m.raw_label}" - {p}',
                    "No value could be read for this year. It will NOT be estimated.", row_id=rid, period=p,
                    category=m.category, resolvable=True)

    # 6. Extraction issues
    for issue in ws.extraction.issues:
        add("extraction", Status.REVIEW_REQUIRED, f"Extraction issue on page {issue.get('page')}",
            f"{issue.get('document', '')}: {issue.get('label')}: {issue.get('detail')}")

    # 7. Identity reconciliations (engine preview)
    inputs, reported = ws.engine_inputs()
    if inputs:
        preview = aengine.build_model(periods, inputs, reported)
        by_id: dict[str, list[dict]] = {}
        for rec in preview["identities"]:
            by_id.setdefault(rec["id"], []).append(rec)
        for ident_id, recs in by_id.items():
            bad = [r for r in recs if not r["matches"]]
            name = recs[0].get("name") or (BY_KEY[recs[0]["reported_category"]].name.replace(" (as reported)", "")
                                           + " reconciles to its components")
            evidence = [{"period": r["period"], "reported": r["reported"], "computed": r["computed"],
                         "variance": r["variance"]} for r in (bad or recs)]
            if bad:
                add("reconciliation", Status.WARNING, f"{name}: break in {len(bad)} of {len(recs)} year(s)",
                    "The engine's recomputed value differs from the printed figure beyond rounding tolerance. "
                    "Engine values are used; a consistent break usually means a line is unmapped or mapped to the "
                    "wrong category.", category=recs[0]["reported_category"], evidence=evidence)
            else:
                add("reconciliation", Status.VALID, name,
                    f"Recomputed value matches the printed figure in all {len(recs)} year(s) (within rounding).",
                    category=recs[0]["reported_category"], evidence=evidence)

    # 8. Restatements between overlapping reports
    by_cat: dict[str, list[dict]] = {}
    for r in ws.restatements():
        by_cat.setdefault(r["category"], []).append(r)
    for cat, items in by_cat.items():
        add("restatement", Status.WARNING, f"{BY_KEY[cat].name} restated in a later report",
            f"The later report's figure is used. Earlier: {items[0]['original_document']}; later: "
            f"{items[0]['restated_document']}.", category=cat,
            evidence=[{"period": i["period"], "reported": i["original"], "computed": i["restated"],
                       "variance": i["difference"]} for i in items])

    # 9. Reviewer interventions
    for r in ws.resolutions:
        if r.type == "value" and r.row_id in ws.rows:
            add("manual_entry", Status.WARNING, f'Reviewer-entered value: "{ws.rows[r.row_id].label}" - {r.period}',
                f"{r.value:,.2f} entered manually. Justification: {r.note}", row_id=r.row_id, period=r.period,
                evidence=[{"resolution_id": r.id}])

    resolved = {(r.row_id, r.period) for r in ws.resolutions if r.type == "value"}
    for c in checks:
        if c.check == "missing_value" and (c.row_id, c.period) in resolved:
            c.resolved = True
    return checks


def incomplete_metrics(model: dict) -> list[dict]:
    return [i for i in aengine.incomplete(model) if i["status"] != CalcStatus.DETERMINISTIC.value]
