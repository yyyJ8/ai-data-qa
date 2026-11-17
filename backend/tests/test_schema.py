"""Schema 目录与召回测试。"""

from pathlib import Path

import pytest

from app.sql.guard import connect_readonly
from app.sql.schema import DIM_TABLES, catalog_mismatch, recall, render_ddl

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND / "data" / "warehouse.db"

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="业务库未初始化")


def test_catalog_matches_database():
    conn = connect_readonly(DB_PATH)
    try:
        assert catalog_mismatch(conn) == []
    finally:
        conn.close()


def test_recall_always_includes_dimensions():
    tables = recall("今天天气怎么样")
    assert set(DIM_TABLES).issubset(tables)
    assert tables != []


@pytest.mark.parametrize(
    "question,expected",
    [
        ("2026年各经营单元收入排名", "fact_revenue"),
        ("完成率低于80%的单元", "fact_target"),
        ("2026年每月合同金额趋势", "fact_order"),
        ("回款缺口最大的单元", "fact_collection"),
        ("高风险项目有哪些", "fact_ppl"),
    ],
)
def test_recall_hits_business_tables(question, expected):
    assert expected in recall(question)


def test_render_ddl_contains_comments_and_columns():
    ddl = render_ddl(["fact_revenue"])
    assert "fact_revenue" in ddl
    assert "revenue" in ddl and "不含税收入" in ddl
    assert "--" in ddl
