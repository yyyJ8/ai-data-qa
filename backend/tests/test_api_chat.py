"""问数 SSE 接口测试：用假 answer 避免真实调用模型。"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api import chat
from app.api.deps import get_store
from app.db.app_store import AppStore
from app.main import app
from app.services.qa import QAResult


@pytest.fixture()
def store(tmp_path):
    s = AppStore(tmp_path / "app.db")
    s.init()
    return s


@pytest.fixture()
def client(store):
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def parse_events(lines: list[str]) -> list[tuple[str, dict]]:
    events, name = [], None
    for line in lines:
        if line.startswith("event: "):
            name = line[len("event: "):]
        elif line.startswith("data: ") and name:
            events.append((name, json.loads(line[len("data: "):])))
            name = None
    return events


def fake_ok(question: str, **kwargs) -> QAResult:
    return QAResult(
        question=question,
        tables=["dim_unit", "fact_revenue"],
        sql="SELECT unit_name FROM dim_unit LIMIT 5",
        chart="bar",
        explanation="按单元列出",
        columns=["unit_name"],
        rows=[["北京代表处"], ["上海代表处"]],
        elapsed_ms=1200,
        prompt_tokens=100,
        completion_tokens=50,
        attempts=1,
    )


def test_chat_streams_expected_events(client, monkeypatch):
    monkeypatch.setattr(chat, "run_answer", fake_ok)
    monkeypatch.setattr(chat, "build_client", lambda store, settings: object())

    with client.stream("POST", "/api/chat", json={"question": "各经营单元收入"}) as resp:
        assert resp.status_code == 200
        events = parse_events(list(resp.iter_lines()))

    names = [e[0] for e in events]
    assert names[0] == "session"
    assert "stage" in names and "table" in names and "done" in names
    table = dict(events)["table"]
    assert table["columns"] == ["unit_name"]
    assert len(table["rows"]) == 2
    assert dict(events)["chart"]["type"] == "bar"
    assert dict(events)["done"]["sql"].startswith("SELECT")


def test_chat_persists_messages(client, store, monkeypatch):
    monkeypatch.setattr(chat, "run_answer", fake_ok)
    monkeypatch.setattr(chat, "build_client", lambda store, settings: object())

    with client.stream("POST", "/api/chat", json={"question": "各经营单元收入"}) as resp:
        events = parse_events(list(resp.iter_lines()))

    session_id = dict(events)["session"]["session_id"]
    messages = store.list_messages(session_id)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["sql"].startswith("SELECT")
    assert messages[1]["meta"]["elapsed_ms"] == 1200


def test_chat_continues_existing_session(client, store, monkeypatch):
    monkeypatch.setattr(chat, "run_answer", fake_ok)
    monkeypatch.setattr(chat, "build_client", lambda store, settings: object())
    sid = store.create_session("已有会话")["session_id"]

    with client.stream("POST", "/api/chat", json={"question": "再问一次", "session_id": sid}) as resp:
        events = parse_events(list(resp.iter_lines()))

    assert dict(events)["session"]["session_id"] == sid
    assert len(store.list_messages(sid)) == 2


def test_chat_reports_error_from_pipeline(client, store, monkeypatch):
    def fake_fail(question: str, **kwargs) -> QAResult:
        return QAResult(question=question, sql="SELECT bad", error="no such table: bad")

    monkeypatch.setattr(chat, "run_answer", fake_fail)
    monkeypatch.setattr(chat, "build_client", lambda store, settings: object())

    with client.stream("POST", "/api/chat", json={"question": "错误问题"}) as resp:
        events = parse_events(list(resp.iter_lines()))

    names = [e[0] for e in events]
    assert "error" in names
    assert names[-1] == "done"
    error = dict(events)["error"]
    assert "bad" in error["message"]


def test_chat_rejects_empty_question(client):
    assert client.post("/api/chat", json={"question": ""}).status_code == 422
