"""会话接口测试。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_store
from app.db.app_store import AppStore
from app.main import app


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


def test_create_and_list_session(client):
    created = client.post("/api/sessions", json={"title": "测试会话"}).json()
    assert created["session_id"] > 0

    listed = client.get("/api/sessions").json()
    assert len(listed) == 1
    assert listed[0]["title"] == "测试会话"
    assert listed[0]["message_count"] == 0


def test_get_session_detail(client):
    sid = client.post("/api/sessions", json={"title": "详情"}).json()["session_id"]
    detail = client.get(f"/api/sessions/{sid}").json()
    assert detail["session_id"] == sid
    assert detail["messages"] == []


def test_rename_and_pin(client):
    sid = client.post("/api/sessions", json={"title": "旧名"}).json()["session_id"]
    updated = client.patch(f"/api/sessions/{sid}", json={"title": "新名", "pinned": True}).json()
    assert updated["title"] == "新名"
    assert updated["pinned"] == 1


def test_delete_session(client):
    sid = client.post("/api/sessions", json={"title": "待删"}).json()["session_id"]
    assert client.delete(f"/api/sessions/{sid}").status_code == 204
    assert client.get(f"/api/sessions/{sid}").status_code == 404


def test_missing_session_returns_404(client):
    assert client.get("/api/sessions/99999").status_code == 404
    assert client.patch("/api/sessions/99999", json={"title": "x"}).status_code == 404


def test_delete_cascades_messages(store):
    session = store.create_session("级联")
    store.add_message(session["session_id"], "user", "问题")
    assert len(store.list_messages(session["session_id"])) == 1
    store.delete_session(session["session_id"])
    assert store.list_messages(session["session_id"]) == []
