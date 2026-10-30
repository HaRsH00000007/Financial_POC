"""GroqProvider behaviour against a scripted fake client (no network, no API key)."""
import json
import logging
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import llm
from app.services.workspace import STORE

logging.disable(logging.INFO)
client = TestClient(app)


def _msg(content=None, tool_calls=None):
    return NS(content=content, tool_calls=tool_calls)


def _tool_call(id_, name, args):
    return NS(id=id_, type="function", function=NS(name=name, arguments=json.dumps(args)))


class FakeCompletions:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return NS(choices=[NS(message=self.script.pop(0))])


def _provider(script):
    p = llm.GroqProvider.__new__(llm.GroqProvider)
    p.model = "test-model"
    p.client = NS(chat=NS(completions=FakeCompletions(script)))
    return p


@pytest.fixture
def ws():
    d = client.post("/api/workspaces/demo").json()
    misc = next(r["id"] for r in d["rows"] if r["label"].startswith("Misc"))
    travel = next(r["id"] for r in d["rows"] if r["label"].startswith("Travel"))
    client.put(f"/api/workspaces/{d['id']}/mappings", json=[{"row_id": misc, "category": "other_opex"}])
    client.post(f"/api/workspaces/{d['id']}/resolutions",
                json={"type": "value", "row_id": travel, "period": "2026-02", "value": 7600, "note": "tie-out"})
    client.post(f"/api/workspaces/{d['id']}/calculate")
    return STORE.get(d["id"])


def test_assistant_tool_loop_uses_engine_tools(ws):
    p = _provider([
        _msg(tool_calls=[_tool_call("c1", "rank_months", {"metric": "revenue", "order": "desc", "top": 1})]),
        _msg(content="Peak revenue was Apr 2026 at $1.32M."),
    ])
    out = p.assistant(ws, "What was our highest revenue month?", [])
    assert out["answer"].startswith("Peak revenue")
    assert out["tool_calls"][0]["tool"] == "rank_months"
    second = p.client.chat.completions.requests[1]["messages"]
    tool_msg = next(m for m in second if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "c1" and "2026-04" in tool_msg["content"]
    assert p.client.chat.completions.requests[0]["tools"][0]["type"] == "function"


def test_bad_tool_arguments_are_reported_not_executed(ws):
    bad = NS(id="c1", type="function", function=NS(name="get_metric", arguments="{not json"))
    p = _provider([_msg(tool_calls=[bad]), _msg(content="Sorry, I could not retrieve that.")])
    out = p.assistant(ws, "EBITDA?", [])
    assert "Invalid tool arguments" in out["tool_calls"][0]["result"]["error"]


def test_mapping_suggestions_reject_invented_categories():
    p = _provider([_msg(content=json.dumps({"mappings": [
        {"label": "Misc adj", "category": "other_opex", "confidence": 0.8, "rationale": "misc expense"},
        {"label": "Weird", "category": "made_up_category", "confidence": 0.9, "rationale": "x"},
        {"label": "Not asked", "category": "revenue", "confidence": 0.9, "rationale": "x"},
    ]}))])
    out = p.suggest_mappings(["Misc adj", "Weird"])
    assert [m["category"] for m in out] == ["other_opex"]
    assert p.client.chat.completions.requests[0]["response_format"] == {"type": "json_object"}


def test_invented_number_in_live_answer_is_replaced(ws, monkeypatch):
    p = _provider([
        _msg(tool_calls=[_tool_call("c1", "get_kpis", {})]),
        _msg(content="Revenue was $99.99M this year."),  # not an engine value
    ])
    monkeypatch.setattr(llm, "_provider", p)
    r = client.post(f"/api/workspaces/{ws.id}/assistant", json={"question": "What was revenue?"}).json()
    assert "99.99" not in r["answer"]
    assert r["numeric_check"]["passed"]
    assert "not traceable" in r["note"]
    monkeypatch.setattr(llm, "_provider", None)


def test_invented_number_in_commentary_is_replaced(ws, monkeypatch):
    p = _provider([_msg(content="EBITDA margin expanded to 31.4% on revenue of $20.1M.")])
    monkeypatch.setattr(llm, "_provider", p)
    c = client.post(f"/api/workspaces/{ws.id}/commentary").json()
    assert "31.4" not in c["text"] and c["numeric_check"]["passed"]
    assert "replaced with the deterministic template" in c["note"]
    monkeypatch.setattr(llm, "_provider", None)
