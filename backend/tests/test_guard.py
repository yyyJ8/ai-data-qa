"""SQL 安全层测试：静态校验 + 运行时只读执行。"""

import json
import sqlite3
from pathlib import Path

import pytest

from app.sql.guard import (
    SqlDeniedError,
    SqlTimeoutError,
    UnsafeSqlError,
    connect_readonly,
    ensure_safe,
    execute_readonly,
    list_tables,
)

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND / "data" / "warehouse.db"
CASES = BACKEND.parent / "samples" / "eval_cases.jsonl"


# --------------------------------------------------------------------------
# 静态校验
# --------------------------------------------------------------------------

def test_adds_limit_when_missing():
    result = ensure_safe("SELECT unit_name FROM dim_unit", max_rows=50)
    assert result.sql.endswith("LIMIT 50")
    assert result.limited is True


def test_clamps_oversized_limit():
    result = ensure_safe("SELECT unit_name FROM dim_unit LIMIT 9999", max_rows=50)
    assert result.sql.endswith("LIMIT 50")
    assert result.clamped is True


def test_keeps_limit_within_bound():
    result = ensure_safe("SELECT unit_name FROM dim_unit LIMIT 10", max_rows=50)
    assert result.sql.endswith("LIMIT 10")
    assert not result.limited and not result.clamped


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE dim_unit",
        "DELETE FROM dim_unit",
        "UPDATE dim_unit SET unit_name = 'x'",
        "INSERT INTO dim_unit VALUES (1, 'x', 'y', 'z')",
        "PRAGMA table_info(dim_unit)",
        "ATTACH DATABASE 'evil.db' AS evil",
        "VACUUM",
        "SELECT 1; DROP TABLE dim_unit",
        "WITH x AS (DELETE FROM dim_unit) SELECT 1",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM dim_unit WHERE unit_id = ?",
        "SELECT load_extension('evil')",
    ],
)
def test_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSqlError):
        ensure_safe(sql, max_rows=100)


def test_ignores_keywords_inside_literals_and_comments():
    ok = "SELECT 'delete from x' AS note FROM dim_unit -- drop table y\n LIMIT 5"
    result = ensure_safe(ok, max_rows=50)
    assert "LIMIT 5" in result.sql


def test_allows_cte_and_chinese_alias():
    sql = "WITH t AS (SELECT unit_id FROM dim_unit) SELECT unit_id AS 单元 FROM t"
    assert "LIMIT" in ensure_safe(sql, max_rows=10).sql


# --------------------------------------------------------------------------
# 运行时只读
# --------------------------------------------------------------------------

pytestmark_db = pytest.mark.skipif(not DB_PATH.exists(), reason="业务库未初始化")


@pytestmark_db
def test_execute_returns_rows():
    conn = connect_readonly(DB_PATH)
    try:
        allowed = list_tables(conn)
        result = execute_readonly(
            conn, "SELECT COUNT(*) AS n FROM dim_unit", max_rows=10, allowed_tables=allowed
        )
        assert result.columns == ["n"]
        assert result.rows[0][0] == 21
    finally:
        conn.close()


@pytestmark_db
def test_rejects_table_outside_whitelist():
    conn = connect_readonly(DB_PATH)
    try:
        with pytest.raises(SqlDeniedError):
            execute_readonly(
                conn,
                "SELECT COUNT(*) FROM fact_revenue",
                max_rows=10,
                allowed_tables=["dim_unit"],
            )
    finally:
        conn.close()


@pytestmark_db
def test_blocks_write_even_if_static_check_bypassed():
    """绕过 ensure_safe 直接交给授权器，写操作仍然被拒。"""
    conn = connect_readonly(DB_PATH)
    try:
        conn.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY)
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("SELECT 1")
    finally:
        conn.set_authorizer(None)
        conn.close()


@pytestmark_db
def test_timeout_aborts_long_query():
    conn = connect_readonly(DB_PATH)
    try:
        allowed = list_tables(conn)
        sql = (
            "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x<100000000) "
            "SELECT COUNT(*) FROM c"
        )
        with pytest.raises(SqlTimeoutError):
            execute_readonly(conn, sql, max_rows=10, timeout_ms=150, allowed_tables=allowed)
    finally:
        conn.close()


@pytestmark_db
def test_respects_row_limit():
    conn = connect_readonly(DB_PATH)
    try:
        allowed = list_tables(conn)
        result = execute_readonly(
            conn, "SELECT unit_id FROM dim_unit", max_rows=5, allowed_tables=allowed
        )
        assert len(result.rows) == 5
        assert result.row_limit == 5
    finally:
        conn.close()


# --------------------------------------------------------------------------
# 与真实语料对齐：30 条评测 SQL 必须全部通过
# --------------------------------------------------------------------------

@pytestmark_db
def test_all_eval_cases_pass_guard_and_execute():
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert cases, "评测集为空"

    conn = connect_readonly(DB_PATH)
    try:
        allowed = list_tables(conn)
        for case in cases:
            guard = ensure_safe(case["sql"], max_rows=200)
            result = execute_readonly(conn, guard.sql, max_rows=200, allowed_tables=allowed)
            assert result.rows, f"{case['id']} 返回 0 行"
    finally:
        conn.close()
