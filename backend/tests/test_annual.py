"""Annual-report (RAG) module: parser, locator, mapper, engine, restatements, AI guards.

A synthetic two-report company is generated in-test (page text, no PDF needed);
real RIL reports in ../docs are exercised when present.
"""
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.annual import assistant, insights
from app.annual import pipeline as ap
from app.annual.insights import indian, verify_verbatim
from app.annual.rag import BM25Index, chunk_pages
from app.annual.statements import classify_page, detect_periods, locate, parse_statement
from app.annual.taxonomy import map_annual_row
from app.main import app

logging.disable(logging.INFO)
client = TestClient(app)
DOCS = Path(__file__).resolve().parents[2] / "docs"


# --------------------------------------------------------------------------- #
# Synthetic company
# --------------------------------------------------------------------------- #
def amt(v: float) -> str:
    if v == 0:
        return "-"
    return f"({indian(abs(v))})" if v < 0 else indian(v)


def fy(end: int) -> str:
    return f"{end - 1}-{str(end)[2:]}"


def pl_page(cur: int, d: dict) -> str:
    y = [cur, cur - 1]
    lines = ["Consolidated Statement of Profit and Loss", f"For the year ended 31st March, {cur}", "(₹ in crore)",
             f"Notes {fy(cur)} {fy(cur - 1)}", "Income"]
    tot = {}
    for e in y:
        x = d[e]
        ti = x["rev"] + x["oi"]
        te = x["mat"] + x["pur"] + x["inv"] + x["emp"] + x["fin"] + x["dep"] + x["oth"]
        pbt = ti - te
        tot[e] = dict(ti=ti, te=te, pbt=pbt, pat=pbt - x["ctax"] - x["dtax"],
                      profit=pbt - x["ctax"] - x["dtax"] + x.get("assoc", 0))

    def row(label, key, note="", src=None):
        vals = [(src or d)[e][key] for e in y]
        return f"{label} {note + ' ' if note else ''}{amt(vals[0])} {amt(vals[1])}"

    lines += [row("Revenue from Operations", "rev", "25"), row("Other Income", "oi", "26"),
              row("Total Income", "ti", src=tot), "Expenses",
              row("Cost of Materials Consumed", "mat"), row("Purchase of Stock-in-Trade", "pur"),
              row("Changes in Inventories of Finished Goods, Work-in-Progress and Stock-in-Trade", "inv", "27"),
              row("Employee Benefits Expense", "emp", "28"), row("Finance Costs", "fin", "29"),
              row("Depreciation / Amortisation and Depletion Expense", "dep", "1"), row("Other Expenses", "oth", "30"),
              row("Total Expenses", "te", src=tot),
              row("Profit Before Share of Profit / (Loss) of Associates / Joint Ventures and Tax", "pbt", src=tot),
              "Tax Expenses", row("Current Tax", "ctax", "13"), row("Deferred Tax", "dtax", "13"),
              row("Profit After Tax", "pat", src=tot)]
    if any("assoc" in d[e] for e in y):
        lines.append(f"Share of Profit / (Loss) of Associates and Joint Ventures {amt(d[y[0]].get('assoc', 0))} "
                     f"{amt(d[y[1]].get('assoc', 0))}")
    lines += [row("Profit for the year", "profit", src=tot), "Material Accounting Policies A-C"]
    return "\n".join(lines)


def bs_page(cur: int, d: dict) -> str:
    y = [cur, cur - 1]
    t = {}
    for e in y:
        x = d[e]
        nca = x["ppe"] + x["ninv"]
        ca = x["stock"] + x["cinv"] + x["tr"] + x["cash"] + x["oca"]
        eq = x["sc"] + x["oe"]
        cl = x["bc"] + x["tp"] + x["ocl"]
        t[e] = dict(nca=nca, ca=ca, ta=nca + ca, eq=eq, ncl=x["bnc"], cl=cl, tl=x["bnc"] + cl, tel=eq + x["bnc"] + cl)

    def row(label, key, note="", src=None):
        vals = [(src or d)[e][key] for e in y]
        return f"{label} {note + ' ' if note else ''}{amt(vals[0])} {amt(vals[1])}"

    return "\n".join([
        "Consolidated Balance Sheet", f"As at 31st March, {cur}", "(₹ in crore)", "Notes As at",
        f"31st March, {cur}", "As at", f"31st March, {cur - 1}", "Assets", "Non-Current Assets",
        row("Property, Plant and Equipment", "ppe", "1"), row("Investments", "ninv", "2"),
        row("Total Non-Current Assets", "nca", src=t), "Current Assets", row("Inventories", "stock", "7"),
        row("Investments", "cinv", "8"), row("Trade Receivables", "tr", "9"),
        row("Cash and Cash Equivalents", "cash", "10"), row("Other Current Assets", "oca", "12"),
        row("Total Current Assets", "ca", src=t), row("Total Assets", "ta", src=t), "Equity and Liabilities",
        "Equity", row("Equity Share Capital", "sc", "14"), row("Other Equity", "oe", "15"),
        row("Total Equity", "eq", src=t), "Non-Current Liabilities", row("Borrowings", "bnc", "16"),
        row("Total Non-Current Liabilities", "ncl", src=t), "Current Liabilities", row("Borrowings", "bc", "20"),
        row("Trade Payables", "tp", "21"), row("Other Current Liabilities", "ocl", "23"),
        row("Total Current Liabilities", "cl", src=t), row("Total Liabilities", "tl", src=t),
        row("Total Equity and Liabilities", "tel", src=t), "As per our Report of even date"])


def cf_page(cur: int, d: dict) -> str:
    y = [cur, cur - 1]
    t = {}
    for e in y:
        x = d[e]
        cfi = x["capex"] + x["pinv"]
        net = x["cash"] - x["open"]
        cff = net - x["cfo"] - cfi
        t[e] = dict(cfi=cfi, cff=cff, net=net, other=cff - x["div"] - x["intp"])

    def row(label, key, src=None):
        vals = [(src or d)[e][key] for e in y]
        return f"{label} {amt(vals[0])} {amt(vals[1])}"

    return "\n".join([
        "Consolidated Statement of Cash Flows", f"For the year ended 31st March, {cur}", "(₹ in crore)",
        f"{fy(cur)} {fy(cur - 1)}", "A. Cash Flow from Operating Activities",
        row("Net Profit Before Tax as per Statement of Profit and Loss", "pbt"),
        row("Depreciation / Amortisation and Depletion Expense", "dep"), row("Finance Costs", "fin"),
        row("Trade and Other Receivables", "wc1"), row("Inventories", "wc2"), row("Taxes Paid (Net)", "taxp"),
        row("Net Cash Flow from Operating Activities", "cfo"), "B. Cash Flow from Investing Activities",
        row("Expenditure for Property, Plant and Equipment and Other Intangible Assets", "capex"),
        row("Purchase of Investments", "pinv"), row("Net Cash Used in Investing Activities", "cfi", src=t),
        "C. Cash Flow from Financing Activities", row("Repayment of Borrowings (Net)", "other", src=t),
        row("Dividend Paid", "div"), row("Interest Paid", "intp"),
        row("Net Cash Flow from / (used in) Financing Activities", "cff", src=t),
        row("Net Increase in Cash and Cash Equivalents", "net", src=t),
        row("Opening Balance of Cash and Cash Equivalents", "open"),
        row("Closing Balance of Cash and Cash Equivalents (Refer Note 10)", "cash"), "As per our Report of even date"])


def year(rev, oth, cash, open_, assoc=None):
    x = dict(rev=rev, oi=5_000, mat=50_000, pur=10_000, inv=-1_000, emp=8_000, fin=2_000, dep=5_000, oth=oth,
             ctax=4_000, dtax=1_000, ppe=60_000, ninv=5_000, stock=8_000, cinv=3_000, tr=4_000, cash=cash, oca=1_000,
             sc=1_000, bnc=20_000, bc=5_000, tp=9_000, ocl=2_000, capex=-12_000, pinv=-2_000, cfo=22_000,
             open=open_, div=-1_000, intp=-2_000, pbt=20_000, wc1=-500, wc2=-1_000, taxp=-4_500)
    x["oe"] = (x["ppe"] + x["ninv"] + x["stock"] + x["cinv"] + x["tr"] + x["cash"] + x["oca"]) - \
              (x["sc"] + x["bnc"] + x["bc"] + x["tp"] + x["ocl"])
    if assoc is not None:
        x["assoc"] = assoc
    return x


NARRATIVE = [
    "Example Industries Limited Annual Report\nChairman's message: our strategy focuses on renewable energy "
    "expansion and digital services growth. The outlook for the coming year remains positive.",
    "Risk management\nKey risks include commodity price volatility, regulatory changes and foreign exchange "
    "headwinds. The Board reviews these risks every quarter.",
]


def report(cur: int, data: dict) -> list[str]:
    standalone = pl_page(cur, data).replace("Consolidated", "Standalone")
    return NARRATIVE + [standalone, pl_page(cur, data), bs_page(cur, data), cf_page(cur, data)]


@pytest.fixture
def synthetic(monkeypatch):
    # FY2025 other expenses printed as 10,200 in the 2025 report, restated to 10,000 in the 2026 report.
    r2025 = {2025: year(90_000, 10_200, 5_000, 3_000), 2024: year(85_000, 9_500, 3_000, 2_000)}
    r2026 = {2026: year(1_00_000, 11_000, 6_000, 5_000, assoc=100), 2025: year(90_000, 10_000, 5_000, 3_000, assoc=0)}
    payload = {"2025.pdf": report(2025, r2025), "2026.pdf": report(2026, r2026)}
    monkeypatch.setattr(ap, "page_texts", lambda data: (json.loads(data), "test-text"))
    files = [(json.dumps(payload[n]).encode(), n) for n in ("2026.pdf", "2025.pdf")]
    return ap.ingest_reports(files)


# --------------------------------------------------------------------------- #
# Unit tests
# --------------------------------------------------------------------------- #
def test_parser_indian_grouping_notes_brackets_and_nil():
    text = "\n".join(["(₹ in crore)", "Notes 2025-26 2024-25", "Income",
                      "Revenue from Operations 25 10,75,675 9,80,136",
                      "Changes in Inventories of Finished Goods, Work-in-Progress and Stock-in-Trade 27 (10,267) (15,124)",
                      "Profit from Discontinued Operations (Net of Tax) - 418",
                      "Net Profit Before Tax as per", "Statement of Profit and Loss", "1,23,162 1,06,017"])
    ps = parse_statement(text, "income_statement", 7)
    assert ps.periods == ["FY2026", "FY2025"] and ps.unit == "crore"
    rows = {r.label: r for r in ps.rows}
    assert rows["Revenue from Operations"].values == {"FY2026": 1075675.0, "FY2025": 980136.0}
    assert rows["Revenue from Operations"].note_ref == "25"
    assert rows["Changes in Inventories of Finished Goods, Work-in-Progress and Stock-in-Trade"].values["FY2026"] == -10267
    assert rows["Profit from Discontinued Operations (Net of Tax)"].values == {"FY2026": 0.0, "FY2025": 418.0}
    joined = rows["Net Profit Before Tax as per Statement of Profit and Loss"]
    assert joined.values["FY2026"] == 123162 and joined.confidence < 0.9


def test_balance_sheet_header_from_march_dates():
    assert detect_periods("Notes As at\n31st March, 2026\nAs at\n31st March, 2025") == ["FY2026", "FY2025"]


def test_mapper_scopes_by_statement_and_section():
    assert map_annual_row("a", "balance_sheet", "Current Liabilities", "Borrowings").category == "borrowings_c"
    assert map_annual_row("b", "balance_sheet", "Non-Current Liabilities", "Borrowings").category == "borrowings_nc"
    pl = map_annual_row("c", "income_statement", "Expenses", "Finance Costs")
    cf = map_annual_row("d", "cash_flow", "Operating Activities", "Finance Costs")
    assert pl.category == "finance_costs" and cf.category == "cf_operating_detail"
    bucket = map_annual_row("e", "balance_sheet", "Current Assets", "Loans")
    assert bucket.category == "ca_other" and bucket.method == "section_rule"


def test_bm25_ranks_relevant_page():
    idx = BM25Index()
    idx.add(chunk_pages("d1", "x.pdf", NARRATIVE, {}))
    hits = idx.search("commodity price risks", k=1)
    assert hits and hits[0][0].page == 2


def test_numeric_guard_is_verbatim():
    allowed = ["₹10,75,675 crore", "19.3%", "+0.6 pp"]
    assert verify_verbatim("Revenue was ₹10,75,675 crore with a 19.3% margin (+0.6 pp) in FY2026.", allowed)["passed"]
    bad = verify_verbatim("Revenue was ₹10,80,000 crore.", allowed)
    assert not bad["passed"] and bad["unverified"] == ["1080000"]


# --------------------------------------------------------------------------- #
# Synthetic end-to-end
# --------------------------------------------------------------------------- #
def test_locator_prefers_consolidated(synthetic):
    rep = synthetic.reports[-1]
    assert rep.statements["income_statement"].page == 4  # page 3 is the standalone copy
    assert rep.statements["income_statement"].scope == "consolidated"
    assert classify_page(rep.pages[0]) is None


def test_synthetic_model_reconciles_and_flags_restatement(synthetic):
    ws = synthetic
    assert ws.extraction.periods == ["FY2024", "FY2025", "FY2026"]
    assert not [m for m in ws.mappings.values() if m.category is None]
    model = ap.calculate(ws)
    assert all(i["matches"] for i in model["identities"]), [i for i in model["identities"] if not i["matches"]]
    # later report's restated figure is used, the difference is flagged
    assert model["values"]["other_expenses"]["FY2025"] == 10_000
    rest = {(r["category"], r["period"]) for r in model["restatements"]}
    assert ("other_expenses", "FY2025") in rest
    assert any(c.check == "restatement" for c in ws.checks)
    # associates only printed in the later report: FY2024 is "not printed", not INCOMPLETE
    assert model["per_period"]["profit"]["FY2024"]["status"] == "DETERMINISTIC"
    assert "associates_share" in model["not_printed"]["FY2024"]
    assert model["per_period"]["profit"]["FY2026"]["result"] == 15_100
    assert model["per_period"]["revenue_growth"]["FY2026"]["result"] == pytest.approx(0.111111, abs=1e-6)


def test_synthetic_lineage_insights_and_assistant(synthetic):
    ws = synthetic
    ap.calculate(ws)
    from app.annual.lineage import build_lineage

    lin = build_lineage(ws, "ebitda", "FY2026")
    assert lin["tree"]["formula"]["formula_id"] == "EBITDA_A01" and lin["pages"] == [4]
    assert lin["documents"] == ["2026.pdf"]
    out = insights.generate(ws)
    assert out["numeric_check"]["passed"] and out["insights"]
    assert out["brief"]["composition"]["narrative_passages"] >= 1
    for q in ["What was EBITDA in FY2026?", "Show me the calculation for net debt", "What are the key risks?",
              "Which numbers were restated?"]:
        a = assistant.answer(ws, q, [])
        assert a["numeric_check"]["passed"], (q, a)
    risks = assistant.answer(ws, "What are the key risks?", [])
    assert any(c["page"] == 2 for c in risks["citations"])
    assert ws.audit.verify()["valid"]


def test_mapping_override_must_stay_on_statement(synthetic):
    rid = next(r for r, m in synthetic.row_meta.items() if m.statement == "cash_flow")
    with pytest.raises(ValueError):
        ap.update_mapping(synthetic, rid, "revenue")


def test_annual_upload_rejects_non_pdf():
    r = client.post("/api/workspaces/annual", files=[("files", ("a.csv", b"x,y", "text/csv"))])
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Real reports (skipped when the PDFs are not in ../docs)
# --------------------------------------------------------------------------- #
RIL = sorted(DOCS.glob("RIL*.pdf"))


@pytest.mark.skipif(len(RIL) < 3, reason="RIL annual reports not present in docs/")
def test_real_reliance_reports():
    ws = ap.ingest_reports([(p.read_bytes(), p.name) for p in RIL])
    assert ws.extraction.periods == ["FY2023", "FY2024", "FY2025", "FY2026"]
    model = ap.calculate(ws)
    assert len(model["identities"]) >= 56 and all(i["matches"] for i in model["identities"])
    assert {(r["category"], r["period"]) for r in model["restatements"]} >= {("cfi", "FY2024")}
    assert model["values"]["revenue"]["FY2026"] == 1075675
    assert model["per_period"]["ebitda"]["FY2026"]["result"] == 207911
