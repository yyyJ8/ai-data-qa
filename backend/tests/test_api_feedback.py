"""反馈（回复校对）接口测试。"""

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


def test_create_and_list_feedback(client):
    created = client.post(
        "/api/feedback", json={"question": "2026年北京收入", "reason": "数据有误"}
    ).json()
    assert created["feedback_id"] > 0

    items = client.get("/api/feedback").json()
    assert len(items) == 1
    assert items[0]["status"] == "待处理"
    assert items[0]["reason"] == "数据有误"


def test_filter_by_status(client):
    client.post("/api/feedback", json={"question": "q1"})
    items = client.get("/api/feedback", params={"status": "已处理"}).json()
    assert items == []


def test_update_status_and_remark(client):
    fid = client.post("/api/feedback", json={"question": "q2"}).json()["feedback_id"]
    updated = client.patch(
        f"/api/feedback/{fid}", json={"status": "已处理", "remark": "已修正"}
    ).json()
    assert updated["status"] == "已处理"
    assert updated["remark"] == "已修正"


def test_update_missing_feedback_404(client):
    assert client.patch("/api/feedback/99999", json={"status": "已处理"}).status_code == 404


def test_invalid_status_rejected(client):
    fid = client.post("/api/feedback", json={"question": "q3"}).json()["feedback_id"]
    assert client.patch(f"/api/feedback/{fid}", json={"status": "乱写"}).status_code == 422
