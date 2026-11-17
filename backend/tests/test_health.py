"""健康检查接口测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_health_exposes_llm_configuration(client):
    body = client.get("/api/health").json()
    assert body["llm"]["model"] == "deepseek-flash"
    assert isinstance(body["llm"]["configured"], bool)
    # 不得泄露密钥
    assert "api_key" not in body["llm"]
    assert "sk-" not in str(body)


def test_warehouse_is_initialized(client):
    warehouse = client.get("/api/health").json()["warehouse"]
    if not warehouse["exists"]:
        pytest.skip("业务库未初始化，先执行 python -m app.db.init_db")
    assert warehouse["tables"] == 10
