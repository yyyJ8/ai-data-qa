"""反馈（回复校对）接口测试。"""

import json
from types import SimpleNamespace

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


# --------------------------------------------------------------------------
# 回灌评测集
# --------------------------------------------------------------------------

def _fake_settings(tmp_path, warehouse):
    return SimpleNamespace(warehouse_path=warehouse, eval_cases_file=tmp_path / "cases.jsonl")


def test_promote_writes_eval_case(client, monkeypatch, tmp_path):
    from app.api import feedback as feedback_api
    from app.core.settings import get_settings

    monkeypatch.setattr(feedback_api, "get_settings", lambda: _fake_settings(tmp_path, get_settings().warehouse_path))

    fid = client.post("/api/feedback", json={"question": "2026年各经营单元名称"}).json()["feedback_id"]
    client.patch(
        f"/api/feedback/{fid}",
        json={"status": "已处理", "corrected_sql": "SELECT unit_name AS 单元 FROM dim_unit"},
    )

    body = client.post(f"/api/feedback/{fid}/promote").json()
    assert body["case_id"] == "q01"
    assert body["rows"] == 21

    lines = (tmp_path / "cases.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    case = json.loads(lines[0])
    assert case["question"] == "2026年各经营单元名称"
    assert case["tags"] == ["from_feedback"]


def test_promote_twice_conflicts(client, monkeypatch, tmp_path):
    from app.api import feedback as feedback_api
    from app.core.settings import get_settings

    monkeypatch.setattr(feedback_api, "get_settings", lambda: _fake_settings(tmp_path, get_settings().warehouse_path))
    fid = client.post("/api/feedback", json={"question": "重复提升"}).json()["feedback_id"]
    client.patch(f"/api/feedback/{fid}", json={"corrected_sql": "SELECT 1 AS x FROM dim_unit"})
    assert client.post(f"/api/feedback/{fid}/promote").status_code == 200
    assert client.post(f"/api/feedback/{fid}/promote").status_code == 409


def test_promote_requires_sql(client):
    fid = client.post("/api/feedback", json={"question": "没有修正 SQL"}).json()["feedback_id"]
    assert client.post(f"/api/feedback/{fid}/promote").status_code == 400


def test_promote_rejects_bad_sql(client, monkeypatch, tmp_path):
    from app.api import feedback as feedback_api
    from app.core.settings import get_settings

    monkeypatch.setattr(feedback_api, "get_settings", lambda: _fake_settings(tmp_path, get_settings().warehouse_path))
    fid = client.post("/api/feedback", json={"question": "坏 SQL"}).json()["feedback_id"]
    client.patch(f"/api/feedback/{fid}", json={"corrected_sql": "DELETE FROM dim_unit"})
    resp = client.post(f"/api/feedback/{fid}/promote")
    assert resp.status_code == 400
    assert "不可执行" in resp.json()["detail"]


def test_promote_rejects_duplicate_question(client, monkeypatch, tmp_path):
    from app.api import feedback as feedback_api
    from app.core.settings import get_settings

    monkeypatch.setattr(feedback_api, "get_settings", lambda: _fake_settings(tmp_path, get_settings().warehouse_path))
    (tmp_path / "cases.jsonl").write_text(
        json.dumps({"id": "q01", "question": "已存在问题", "sql": "SELECT 1", "tags": []}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fid = client.post("/api/feedback", json={"question": "已存在问题"}).json()["feedback_id"]
    client.patch(f"/api/feedback/{fid}", json={"corrected_sql": "SELECT 1 AS x FROM dim_unit"})
    assert client.post(f"/api/feedback/{fid}/promote").status_code == 409


def test_next_case_id_increments(client, monkeypatch, tmp_path):
    from app.api import feedback as feedback_api
    from app.core.settings import get_settings

    monkeypatch.setattr(feedback_api, "get_settings", lambda: _fake_settings(tmp_path, get_settings().warehouse_path))
    (tmp_path / "cases.jsonl").write_text(
        "\n".join(
            json.dumps({"id": f"q{i:02d}", "question": f"问题{i}", "sql": "SELECT 1", "tags": []}, ensure_ascii=False)
            for i in range(1, 4)
        )
        + "\n",
        encoding="utf-8",
    )
    fid = client.post("/api/feedback", json={"question": "新问题"}).json()["feedback_id"]
    client.patch(f"/api/feedback/{fid}", json={"corrected_sql": "SELECT 1 AS x FROM dim_unit"})
    assert client.post(f"/api/feedback/{fid}/promote").json()["case_id"] == "q04"
