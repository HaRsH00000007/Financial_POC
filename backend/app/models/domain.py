"""Internal financial data model.

Every numeric value that enters the system is a ``FinancialValue`` carrying a
``SourceReference``. Derived numbers are ``CalculationResult`` objects that carry
the formula that produced them and the exact inputs used. Nothing numeric is
ever produced without one of these two provenance records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Status(str, Enum):
    VALID = "VALID"
    WARNING = "WARNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CalcStatus(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"      # computed from complete inputs
    INCOMPLETE = "INCOMPLETE"            # one or more inputs missing -> no value
    UNDEFINED = "UNDEFINED"              # mathematically undefined (e.g. / 0)


class Document(BaseModel):
    id: str
    filename: str
    file_type: Literal["pdf", "xlsx", "csv"]
    size_bytes: int
    sha256: str
    uploaded_at: str = Field(default_factory=utcnow)
    is_demo: bool = False
    pages: int | None = None
    sheets: list[str] = []


class SourceReference(BaseModel):
    document_id: str
    document_name: str
    page: int | None = None          # PDF page (1-based)
    sheet: str | None = None         # XLSX sheet
    cell: str | None = None          # XLSX cell / CSV row:col
    row_label: str                   # label exactly as it appeared in the source
    raw_text: str | None = None      # raw token as it appeared ("(1,200)", "—")
    extraction_method: str           # e.g. "pdf-text-table", "xlsx-cell", "manual-entry"
    confidence: float                # 0..1 extraction confidence


class FinancialPeriod(BaseModel):
    key: str                         # "2026-01"
    label: str                       # "Jan 2026"


class RawLineItem(BaseModel):
    """A row as extracted from the source, before normalization."""
    id: str
    label: str
    values: dict[str, Optional[float]]           # period key -> value (None = missing in source)
    sources: dict[str, SourceReference]          # period key -> where the value came from
    confidence: float
    notes: list[str] = []


class NormalizedCategory(BaseModel):
    key: str
    name: str
    kind: Literal["input", "reported_subtotal", "memo", "excluded"]
    statement: Literal["income_statement", "balance_sheet", "none"] = "income_statement"
    description: str = ""
    synonyms: list[str] = []


class Mapping(BaseModel):
    row_id: str
    raw_label: str
    category: Optional[str]          # canonical key, None = unmapped
    method: Literal["exact_synonym", "fuzzy_match", "ai_suggested", "user_override", "unmapped"]
    confidence: float
    status: Status
    rationale: str = ""
    alternatives: list[dict[str, Any]] = []


class FinancialValue(BaseModel):
    metric: str
    period: str
    value: Optional[float]
    currency: str = "USD"
    source: Optional[SourceReference] = None
    component_rows: list[str] = []   # raw row ids aggregated into this value
    status: CalcStatus = CalcStatus.DETERMINISTIC


class Formula(BaseModel):
    formula_id: str
    metric: str
    name: str
    expression: str
    inputs: list[str]
    optional_inputs: list[str] = []  # may be omitted when not reported in the source at all
    output_format: Literal["currency", "percent"] = "currency"
    description: str = ""


class CalculationInput(BaseModel):
    name: str
    value: Optional[float]
    kind: Literal["source", "derived"]


class CalculationResult(BaseModel):
    metric: str
    period: str                      # period key, "T12", "T12_PRIOR"
    formula_id: str
    expression: str
    substituted: str                 # expression with numbers substituted
    inputs: list[CalculationInput]
    result: Optional[float]
    status: CalcStatus
    missing_inputs: list[str] = []
    engine: str = "deterministic-decimal-v1"


class ValidationCheck(BaseModel):
    id: str
    check: str
    status: Status
    title: str
    detail: str
    row_id: str | None = None
    category: str | None = None
    period: str | None = None
    resolvable: bool = False
    resolved: bool = False
    evidence: list[dict[str, Any]] = []


class AuditEvent(BaseModel):
    seq: int
    timestamp: str
    actor: Literal["system", "ai", "user", "engine"]
    agent: str | None = None
    event_type: str
    summary: str
    details: dict[str, Any] = {}
    prev_hash: str
    hash: str
