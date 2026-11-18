"""配置接口测试：应用配置与模型配置（含密钥不外泄）。"""

import pytest
from fastapi.testclient import TestClient

from app.api import config as config_api
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


def test_app_config_defaults(client):
    body = client.get("/api/config/app").json()
    assert body["greeting"] is True
    assert isinstance(body["greetingQuestions"], list)
    assert body["hotThreshold"] == 3


def test_app_config_partial_update_keeps_other_keys(client):
    client.put("/api/config/app", json={"greeting": False})
    body = client.get("/api/config/app").json()
    assert body["greeting"] is False
    assert body["hotThreshold"] == 3


def test_app_config_trims_and_caps_questions(client):
    body = client.put(
        "/api/config/app",
        json={"greetingQuestions": [" 问题A ", "", "问题B"]},
    ).json()
    assert body["greetingQuestions"] == ["问题A", "问题B"]


def test_model_config_masks_key(client):
    body = client.get("/api/config/model").json()
    assert "api_key" not in body
    assert "sk-" not in str(body) or "****" in body["api_key_masked"]
    assert body["api_key_masked"].count("*") >= 4


def test_model_config_update_persists(client):
    client.put("/api/config/model", json={"model": "deepseek-flash", "thinking": False})
    body = client.get("/api/config/model").json()
    assert body["model"] == "deepseek-flash"
    assert body["thinking"] is False


def test_model_config_rejects_unknown_effort(client):
    assert client.put("/api/config/model", json={"reasoning_effort": "extreme"}).status_code == 422


def test_model_test_reports_failure_without_network(client, monkeypatch):
    def boom(store, settings):
        raise config_api.LLMError("LLM_API_KEY 未配置")

    monkeypatch.setattr(config_api, "build_client", boom)
    body = client.post("/api/config/model/test").json()
    assert body["ok"] is False
    assert "LLM_API_KEY" in body["error"]
