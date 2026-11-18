"""Ind AS / IFRS annual-statement taxonomy and the rules-first mapper.

Categories are scoped to one statement, so a cash-flow line such as "Finance
Costs" can never be mistaken for the P&L expense. Balance-sheet lines are matched
on "<section> <label>" (e.g. "current liabilities borrowings"). A line that has no
specific category but sits inside a balance-sheet section is assigned to that
section's "other" bucket by a section rule; the printed section totals then prove,
through the reconciliation checks, that nothing was dropped or double counted.

Order of precedence (same contract as the T-12 normalizer):
1. reviewer override  2. exact synonym  3. section rule  4. fuzzy match (WARNING)
5. AI suggestion (WARNING)  6. unmapped (REVIEW REQUIRED)
"""
from __future__ import annotations

from difflib import SequenceMatcher

from app.models.domain import Mapping, NormalizedCategory, Status
from app.normalization.normalizer import clean_label

IS, BS, CF = "income_statement", "balance_sheet", "cash_flow"


def _c(key, name, kind, statement, synonyms=(), description=""):
    return NormalizedCategory(key=key, name=name, kind=kind, statement=statement, synonyms=list(synonyms),
                              description=description)


CATEGORIES: list[NormalizedCategory] = [
    # ---- Statement of Profit and Loss: formula inputs
    _c("revenue", "Revenue from Operations", "input", IS,
       ["revenue from operations", "income revenue from operations", "net revenue from operations"]),
    _c("other_income", "Other Income", "input", IS, ["other income", "income other income"]),
    _c("materials_cost", "Cost of Materials Consumed", "input", IS,
       ["cost of materials consumed", "cost of raw materials consumed", "expenses cost of materials consumed"]),
    _c("purchases_traded", "Purchase of Stock-in-Trade", "input", IS,
       ["purchase of stock-in-trade", "purchases of stock-in-trade", "purchase of stock in trade",
        "purchase of traded goods"]),
    _c("inventory_change", "Changes in Inventories", "input", IS,
       ["changes in inventories of finished goods, work-in-progress and stock-in-trade",
        "changes in inventories of finished goods work-in-progress and stock-in-trade", "changes in inventories"]),
    _c("excise_duty", "Excise Duty", "input", IS, ["excise duty"]),
    _c("employee_costs", "Employee Benefits Expense", "input", IS,
       ["employee benefits expense", "employee benefit expenses", "employee costs"]),
    _c("finance_costs", "Finance Costs", "input", IS, ["finance costs", "finance cost"]),
    _c("depreciation", "Depreciation / Amortisation & Depletion", "input", IS,
       ["depreciation / amortisation and depletion expense", "depreciation and amortisation expense",
        "depreciation amortisation and depletion expense", "depreciation and amortization expense"]),
    _c("other_expenses", "Other Expenses", "input", IS, ["other expenses"]),
    _c("current_tax", "Current Tax", "input", IS, ["current tax", "tax expenses current tax"]),
    _c("deferred_tax", "Deferred Tax", "input", IS, ["deferred tax", "tax expenses deferred tax"]),
    _c("associates_share", "Share of Associates / JVs", "input", IS,
       ["share of profit / (loss) of associates and joint ventures",
        "share of profit / (loss) of associate and joint ventures", "share of profit of associates and joint ventures"]),
    _c("discontinued_profit", "Profit from Discontinued Operations", "input", IS,
       ["profit from discontinued operations (net of tax)", "profit from discontinued operations"]),
    # ---- P&L: printed subtotals (reconciliation only)
    _c("total_income_reported", "Total Income (as reported)", "reported_subtotal", IS, ["total income"]),
    _c("total_expenses_reported", "Total Expenses (as reported)", "reported_subtotal", IS, ["total expenses"]),
    _c("pbt_reported", "Profit Before Associates & Tax (as reported)", "reported_subtotal", IS,
       ["profit before share of profit / (loss) of associates / joint ventures and tax",
        "profit before share of profit of associates joint ventures and tax"]),
    _c("pbt_after_associates_reported", "Profit Before Tax (as reported)", "reported_subtotal", IS,
       ["profit before tax"]),
    _c("profit_reported", "Profit for the Year (as reported)", "reported_subtotal", IS,
       ["profit for the year", "profit for the period", "net profit for the year"]),
    # ---- P&L: memo lines (shown, not used in formulas)
    _c("gross_revenue", "Value of Sales & Services (gross)", "memo", IS,
       ["value of sales & services (revenue)", "value of sales and services (revenue)"]),
    _c("value_of_sales", "Value of Sales", "memo", IS, ["value of sales"]),
    _c("income_from_services", "Income from Services", "memo", IS, ["income from services"]),
    _c("gst_recovered", "GST Recovered", "memo", IS, ["less: gst recovered", "gst recovered"]),
    _c("profit_after_tax_memo", "Profit After Tax (presentation varies)", "memo", IS,
       ["profit after tax", "profit from continuing operations"],
       "Printed before or after the share of associates depending on the year's presentation - memo only."),
    _c("profit_owners", "Profit Attributable to Owners", "memo", IS,
       ["profit attribution owners of the company", "profit attribution a) owners of the company"]),
    _c("profit_nci", "Profit Attributable to NCI", "memo", IS,
       ["profit attribution non-controlling interest", "profit attribution b) non-controlling interest"]),
    _c("eps_basic", "EPS - Basic", "memo", IS, ["basic", "basic (in i)", "basic (in c)", "basic (in h)"]),
    _c("eps_diluted", "EPS - Diluted", "memo", IS, ["diluted", "diluted (in i)", "diluted (in c)", "diluted (in h)"]),
    _c("oci_detail", "Other Comprehensive Income (detail)", "memo", IS,
       ["total other comprehensive income / (loss) for the year (net of tax)",
        "total other comprehensive income / (loss) from continuing operations (net of tax)",
        "total other comprehensive income / (loss) from discontinued operations (net of tax)",
        "total comprehensive income for the year"],
       "Section rule: OCI and comprehensive-income lines are carried for reference."),
    # ---- Balance sheet: formula inputs
    _c("nca_investments", "Non-Current Investments", "input", BS, ["non-current assets investments"]),
    _c("nca_other", "Other Non-Current Assets (bucket)", "input", BS, [],
       "Section rule: every other line printed under Non-Current Assets."),
    _c("inventories", "Inventories", "input", BS, ["current assets inventories"]),
    _c("current_investments", "Current Investments", "input", BS, ["current assets investments"]),
    _c("trade_receivables", "Trade Receivables", "input", BS, ["current assets trade receivables"]),
    _c("cash_equivalents", "Cash and Cash Equivalents", "input", BS, ["current assets cash and cash equivalents"]),
    _c("ca_other", "Other Current Assets (bucket)", "input", BS, [],
       "Section rule: every other line printed under Current Assets."),
    _c("share_capital", "Equity Share Capital", "input", BS, ["equity equity share capital"]),
    _c("other_equity", "Other Equity", "input", BS, ["equity other equity"]),
    _c("nci", "Non-Controlling Interest", "input", BS, ["equity non-controlling interest"]),
    _c("borrowings_nc", "Borrowings - Non-Current", "input", BS, ["non-current liabilities borrowings"]),
    _c("lease_nc", "Lease Liabilities - Non-Current", "input", BS, ["non-current liabilities lease liabilities"]),
    _c("ncl_other", "Other Non-Current Liabilities (bucket)", "input", BS, [],
       "Section rule: every other line printed under Non-Current Liabilities."),
    _c("borrowings_c", "Borrowings - Current", "input", BS, ["current liabilities borrowings"]),
    _c("lease_c", "Lease Liabilities - Current", "input", BS, ["current liabilities lease liabilities"]),
    _c("trade_payables", "Trade Payables", "input", BS, ["current liabilities trade payables"]),
    _c("cl_other", "Other Current Liabilities (bucket)", "input", BS, [],
       "Section rule: every other line printed under Current Liabilities."),
    # ---- Balance sheet: printed subtotals
    _c("total_nca_reported", "Total Non-Current Assets (as reported)", "reported_subtotal", BS,
       ["total non-current assets"]),
    _c("total_ca_reported", "Total Current Assets (as reported)", "reported_subtotal", BS, ["total current assets"]),
    _c("total_assets_reported", "Total Assets (as reported)", "reported_subtotal", BS, ["total assets"]),
    _c("total_equity_reported", "Total Equity (as reported)", "reported_subtotal", BS, ["total equity"]),
    _c("total_ncl_reported", "Total Non-Current Liabilities (as reported)", "reported_subtotal", BS,
       ["total non-current liabilities"]),
    _c("total_cl_reported", "Total Current Liabilities (as reported)", "reported_subtotal", BS,
       ["total current liabilities"]),
    _c("total_liabilities_reported", "Total Liabilities (as reported)", "reported_subtotal", BS,
       ["total liabilities"]),
    _c("total_eq_liab_reported", "Total Equity and Liabilities (as reported)", "reported_subtotal", BS,
       ["total equity and liabilities"]),
    # ---- Cash flow: formula inputs
    _c("cfo", "Net Cash from Operating Activities", "input", CF,
       ["net cash flow from operating activities", "net cash from operating activities",
        "net cash generated from operating activities"]),
    _c("cfi", "Net Cash from Investing Activities", "input", CF,
       ["net cash used in investing activities", "net cash flow used in investing activities",
        "net cash flow from / (used in) investing activities", "net cash flow from investing activities"]),
    _c("cff", "Net Cash from Financing Activities", "input", CF,
       ["net cash flow from / (used in) financing activities", "net cash flow used in financing activities",
        "net cash used in financing activities", "net cash flow from financing activities"]),
    _c("opening_cash", "Opening Cash and Cash Equivalents", "input", CF,
       ["opening balance of cash and cash equivalents"]),
    _c("capex", "Capital Expenditure (cash, as printed)", "input", CF,
       ["expenditure for property, plant and equipment, spectrum and other intangible assets",
        "expenditure for property, plant and equipment and other intangible assets",
        "purchase of property, plant and equipment"]),
    _c("cash_adjust_add", "Cash Added on Acquisition / Other", "input", CF,
       ["add: upon addition of subsidiaries"]),
    _c("cash_adjust_less", "Cash Removed on Demerger / Other", "input", CF,
       ["less: on demerger (refer note 43)", "less: on demerger"]),
    # ---- Cash flow: printed subtotals and memo
    _c("net_change_reported", "Net Change in Cash (as reported)", "reported_subtotal", CF,
       ["net increase in cash and cash equivalents", "net increase / (decrease) in cash and cash equivalents",
        "net (decrease) / increase in cash and cash equivalents"]),
    _c("closing_cash_reported", "Closing Cash (as reported)", "reported_subtotal", CF,
       ["closing balance of cash and cash equivalents (refer note 10)", "closing balance of cash and cash equivalents"]),
    _c("dividends_paid", "Dividends Paid to Shareholders", "memo", CF,
       ["payment of dividend to equity holders of the company", "dividend paid"]),
    _c("interest_paid", "Interest Paid", "memo", CF, ["interest paid"]),
    _c("taxes_paid", "Taxes Paid (Net)", "memo", CF, ["taxes paid (net)"]),
    _c("cf_operating_detail", "Operating Cash-Flow Detail", "memo", CF,
       ["sub-total", "operating profit before working capital changes", "cash generated from operations"],
       "Section rule: detail line under Operating Activities - carried for reference."),
    _c("cf_investing_detail", "Investing Cash-Flow Detail", "memo", CF, [],
       "Section rule: detail line under Investing Activities - carried for reference."),
    _c("cf_financing_detail", "Financing Cash-Flow Detail", "memo", CF, [],
       "Section rule: detail line under Financing Activities - carried for reference."),
    _c("excluded", "Excluded (not used)", "excluded", "none", [], "Explicitly excluded by a reviewer"),
]

BY_KEY = {c.key: c for c in CATEGORIES}

_SECTION_BUCKET = {
    (BS, "Non-Current Assets"): "nca_other", (BS, "Current Assets"): "ca_other",
    (BS, "Non-Current Liabilities"): "ncl_other", (BS, "Current Liabilities"): "cl_other",
    (CF, "Operating Activities"): "cf_operating_detail", (CF, "Investing Activities"): "cf_investing_detail",
    (CF, "Financing Activities"): "cf_financing_detail",
    (IS, "Other Comprehensive Income"): "oci_detail", (IS, "OCI Attribution"): "oci_detail",
    (IS, "TCI Attribution"): "oci_detail",
}
_NOT_BUCKETED = ("total", "net cash", "net increase", "net decrease", "closing balance", "opening balance",
                 "sub-total", "subtotal")

FUZZY_ACCEPT = 0.88
FUZZY_SUGGEST = 0.6


def _syn(statement: str) -> list[tuple[str, str]]:
    return [(clean_label(s), c.key) for c in CATEGORIES if c.statement == statement for s in c.synonyms]


_SYN = {st: _syn(st) for st in (IS, BS, CF)}
_EXACT = {st: {s: k for s, k in pairs} for st, pairs in _SYN.items()}


def qualified(statement: str, section: str, label: str) -> str:
    return f"{section} {label}" if section else label


def candidates(statement: str, section: str, label: str, limit: int = 3) -> list[dict]:
    best: dict[str, float] = {}
    for text in (clean_label(qualified(statement, section, label)), clean_label(label)):
        for syn, key in _SYN.get(statement, []):
            score = SequenceMatcher(None, text, syn).ratio()
            if score > best.get(key, 0):
                best[key] = score
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"category": k, "name": BY_KEY[k].name, "score": round(s, 3)} for k, s in ranked]


def map_annual_row(row_id: str, statement: str, section: str, label: str) -> Mapping:
    exact = _EXACT.get(statement, {})
    for text in (clean_label(qualified(statement, section, label)), clean_label(label)):
        if text in exact:
            key = exact[text]
            return Mapping(row_id=row_id, raw_label=label, category=key, method="exact_synonym", confidence=0.98,
                           status=Status.VALID,
                           rationale=f'"{label}" ({section or "statement"}) is a registered synonym of {BY_KEY[key].name}.')
    bucket = _SECTION_BUCKET.get((statement, section))
    low = label.lower()
    if bucket and not low.startswith(_NOT_BUCKETED):
        return Mapping(row_id=row_id, raw_label=label, category=bucket, method="section_rule", confidence=0.95,
                       status=Status.VALID,
                       rationale=f"Section rule: printed under {section}; assigned to {BY_KEY[bucket].name}. "
                                 "Section totals are reconciled, so a missed or double-counted line is detected.")
    alts = candidates(statement, section, label)
    top = alts[0] if alts else None
    if top and top["score"] >= FUZZY_ACCEPT:
        return Mapping(row_id=row_id, raw_label=label, category=top["category"], method="fuzzy_match",
                       confidence=round(top["score"] * 0.95, 3), status=Status.WARNING,
                       rationale=f'Closest synonym match to {top["name"]} (similarity {top["score"]:.0%}). Confirm the mapping.',
                       alternatives=alts)
    return Mapping(row_id=row_id, raw_label=label, category=None, method="unmapped", confidence=0.0,
                   status=Status.REVIEW_REQUIRED,
                   rationale="No reliable match in the annual-statement taxonomy. A reviewer must map or exclude this row.",
                   alternatives=[a for a in alts if a["score"] >= FUZZY_SUGGEST])
