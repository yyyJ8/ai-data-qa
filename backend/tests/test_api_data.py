"""数据接口测试：分页、过滤、排序、导出。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "warehouse.db"
pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="业务库未初始化")


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_pagination_returns_expected_shape(client):
    body = client.get("/api/data/dim_unit", params={"page": 1, "page_size": 5}).json()
    assert body["total"] == 21
    assert len(body["rows"]) == 5
    assert body["columns"][0] == "unit_id"


def test_second_page_differs(client):
    first = client.get("/api/data/dim_unit", params={"page": 1, "page_size": 5}).json()["rows"]
    second = client.get("/api/data/dim_unit", params={"page": 2, "page_size": 5}).json()["rows"]
    assert first != second


def test_filter_by_keyword(client):
    body = client.get("/api/data/dim_unit", params={"q": "北京", "page_size": 50}).json()
    assert body["total"] >= 1
    assert any("北京" in str(row[1]) for row in body["rows"])


def test_sort_desc(client):
    body = client.get(
        "/api/data/fact_target", params={"sort": "commercial_target", "order": "desc", "page_size": 3}
    ).json()
    values = [row[3] for row in body["rows"]]
    assert values == sorted(values, reverse=True)


def test_unknown_table_404(client):
    assert client.get("/api/data/not_a_table").status_code == 404


def test_invalid_sort_column_400(client):
    assert client.get("/api/data/dim_unit", params={"sort": "hacker"}).status_code == 400


def test_export_returns_xlsx(client):
    resp = client.get("/api/data/dim_unit/export")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert len(resp.content) > 1000
    assert "attachment" in resp.headers["content-disposition"]
