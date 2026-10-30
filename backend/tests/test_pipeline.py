import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.formatting import verify_numeric_claims
from app.services.workspace import STORE

logging.disable(logging.INFO)
client = TestClient(app)


@pytest.fixture(params=["pdf", "xlsx", "csv"])
def demo(request):
    return client.post(f"/api/workspaces/demo?fmt={request.param}").json()


def test_demo_extraction_every_format(demo):
    assert len(demo["periods"]) == 24
    unmapped = [m for m in demo["mappings"].values() if m["category"] is None]
    assert len(unmapped) == 1 and unmapped[0]["raw_label"].startswith("Misc")
    statuses = {c["check"]: c["status"] for c in demo["checks"]}
    assert statuses["missing_value"] == "REVIEW_REQUIRED"
    assert demo["check_summary"]["overall"] == "REVIEW_REQUIRED"


def test_upload_rejects_unsupported_type():
    r = client.post("/api/workspaces/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def _prepared():
    d = client.post("/api/workspaces/demo?fmt=pdf").json()
    wid = d["id"]
    misc = next(r["id"] for r in d["rows"] if r["label"].startswith("Misc"))
    client.put(f"/api/workspaces/{wid}/mappings", json=[{"row_id": misc, "category": "other_opex"}])
    return wid, d


def test_missing_value_blocks_totals_until_resolved():
    wid, d = _prepared()
    m = client.post(f"/api/workspaces/{wid}/calculate").json()
    assert m["model"]["t12"]["net_income"]["result"] is None
    travel = next(r["id"] for r in d["rows"] if r["label"].startswith("Travel"))
    r = client.post(f"/api/workspaces/{wid}/resolutions",
                    json={"type": "value", "row_id": travel, "period": "2026-02", "value": 7600, "note": ""})
    assert r.status_code == 400  # a justification is mandatory
    client.post(f"/api/workspaces/{wid}/resolutions",
                json={"type": "value", "row_id": travel, "period": "2026-02", "value": 7600,
                      "note": "Tied to expense report ER-0226"})
    m = client.post(f"/api/workspaces/{wid}/calculate").json()["model"]
    assert m["t12"]["net_income"]["result"] is not None
    assert all(c["passed"] for c in m["crossfoot"])
    # With the tied-out value, only the typo in the printed Net Income subtotal remains.
    bad = [r for r in m["reconciliations"] if not r["matches"]]
    assert [(b["metric"], b["period"]) for b in bad] == [("net_income", "2026-03")]


def test_lineage_reaches_source_cells():
    wid, _ = _prepared()
    client.post(f"/api/workspaces/{wid}/calculate")
    lin = client.get(f"/api/workspaces/{wid}/lineage", params={"metric": "net_income", "period": "2026-01"}).json()
    assert lin["tree"]["formula"]["formula_id"] == "NI_001"
    assert lin["documents"] == ["meridian_ridge_monthly_pnl_DEMO.pdf"]
    assert all(leaf["source"]["page"] for leaf in lin["leaf_sources"])
    payroll = [leaf for leaf in lin["leaf_sources"] if leaf["category"] == "payroll"]
    assert len(payroll) == 2  # two source rows aggregate into Payroll


def test_ai_outputs_only_contain_engine_numbers():
    wid, _ = _prepared()
    client.post(f"/api/workspaces/{wid}/calculate")
    c = client.post(f"/api/workspaces/{wid}/commentary").json()
    assert c["numeric_check"]["passed"] and c["numeric_check"]["checked"] > 3
    for q in ["What was our highest revenue month?", "Why did EBITDA change?",
              "Show me the calculation for EBITDA", "What expenses increased the most?",
              "Give me a management summary", "Which numbers require review?"]:
        a = client.post(f"/api/workspaces/{wid}/assistant", json={"question": q}).json()
        assert a["numeric_check"]["passed"], (q, a["numeric_check"])
        assert a["tool_calls"], q


def test_numeric_guard_rejects_invented_figures():
    assert verify_numeric_claims("Revenue was $14.49M, up 11.9%.", [14_487_900, 0.11912])["passed"]
    assert not verify_numeric_claims("Revenue was $15.2M.", [14_487_900])["passed"]


def test_audit_chain_is_tamper_evident():
    wid, _ = _prepared()
    client.post(f"/api/workspaces/{wid}/calculate")
    ws = STORE.get(wid)
    assert ws.audit.verify()["valid"]
    ws.audit._events[2].summary = "edited after the fact"
    assert not ws.audit.verify()["valid"]


def test_evaluation_index_is_transparent():
    body = {"platforms": [{"id": "a", "name": "Platform A"}],
            "cells": {"a:financial_accuracy": {"assessment": "strong"},
                      "a:auditability": {"assessment": "partial"}},
            "weights": {"financial_accuracy": 2}}
    s = client.post("/api/evaluation/summary", json=body).json()["platforms"][0]
    assert s["assessed"] == 2
    assert s["index"] == round((2 * 4 + 1 * 2) / (2 * 4 + 1 * 4), 4)
