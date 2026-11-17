"""业务库自检：行数、外键、勾稽关系、可复现性。

用法：
    python -m app.db.verify
    python -m app.db.verify --db D:/x.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

from .init_db import DEFAULT_DB, build

UNITS_EXPECTED = 21
INDUSTRIES_EXPECTED = 14
LINES_EXPECTED = 3

# 完成率允许区间（收入 / 商业目标）
COMPLETION_MIN = 0.45
COMPLETION_MAX = 1.25


def _count(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    return conn.execute(sql, params).fetchone()[0]


def check_rows(conn: sqlite3.Connection) -> tuple[bool, str]:
    checks = {
        "dim_unit": UNITS_EXPECTED,
        "dim_industry": INDUSTRIES_EXPECTED,
        "dim_product_line": LINES_EXPECTED,
    }
    problems = []
    for table, expected in checks.items():
        actual = _count(conn, f"SELECT COUNT(*) FROM {table}")
        if actual != expected:
            problems.append(f"{table}={actual}≠{expected}")
    for table in ("dim_product", "dim_customer", "fact_target", "fact_revenue",
                  "fact_order", "fact_collection", "fact_ppl"):
        if _count(conn, f"SELECT COUNT(*) FROM {table}") == 0:
            problems.append(f"{table} 为空")
    return (not problems, "维度数量正确" if not problems else "; ".join(problems))


def check_foreign_keys(conn: sqlite3.Connection) -> tuple[bool, str]:
    bad = conn.execute("PRAGMA foreign_key_check").fetchall()
    return (not bad, "外键完整" if not bad else f"{len(bad)} 条外键违规")


def check_completion(conn: sqlite3.Connection) -> tuple[bool, str]:
    bad = _count(
        conn,
        """
        SELECT COUNT(*) FROM (
            SELECT t.year, t.unit_id, t.product_line_id,
                   SUM(r.revenue) * 1.0 / t.commercial_target AS rate
            FROM fact_target t
            JOIN fact_revenue r
              ON r.unit_id = t.unit_id
             AND r.product_line_id = t.product_line_id
             AND substr(r.month, 1, 4) = CAST(t.year AS TEXT)
            GROUP BY t.year, t.unit_id, t.product_line_id, t.commercial_target
            HAVING rate < ? OR rate > ?
        )
        """,
        (COMPLETION_MIN, COMPLETION_MAX),
    )
    return (bad == 0, "完成率全部落在 45%–125%" if bad == 0 else f"{bad} 个组合完成率越界")


def check_order_vs_revenue(conn: sqlite3.Connection) -> tuple[bool, str]:
    order_total = _count(conn, "SELECT COALESCE(SUM(amount), 0) FROM fact_order")
    revenue_total = _count(conn, "SELECT COALESCE(SUM(contract_amount), 0) FROM fact_revenue")
    ok = order_total == revenue_total
    return (ok, f"合同额合计 订单={order_total} 收入表={revenue_total}")


def check_monthly_sums(conn: sqlite3.Connection) -> tuple[bool, str]:
    bad = _count(
        conn,
        """
        SELECT COUNT(*) FROM (
            SELECT unit_id, product_line_id, substr(month, 1, 4) AS y, SUM(revenue) AS total
            FROM fact_revenue
            GROUP BY unit_id, product_line_id, substr(month, 1, 4)
            HAVING total <= 0
        )
        """,
    )
    return (bad == 0, "月度合计均大于 0" if bad == 0 else f"{bad} 个组合月合计为 0")


def check_collection(conn: sqlite3.Connection) -> tuple[bool, str]:
    bad = _count(conn, "SELECT COUNT(*) FROM fact_collection WHERE actual_amount > plan_amount * 1.05")
    return (bad == 0, "回款不超过计划 105%" if bad == 0 else f"{bad} 条回款异常")


def check_target_sol(conn: sqlite3.Connection) -> tuple[bool, str]:
    bad = _count(
        conn,
        """
        SELECT COUNT(*) FROM fact_target
        WHERE (product_line_id = 3 AND sol_target IS NULL)
           OR (product_line_id <> 3 AND sol_target IS NOT NULL)
        """,
    )
    return (bad == 0, "商解目标仅落在商业解决方案行" if bad == 0 else f"{bad} 行商解目标不符合约定")


def _fingerprint(db_path: Path) -> tuple[int, int, int, int]:
    conn = sqlite3.connect(db_path)
    try:
        return (
            _count(conn, "SELECT COUNT(*) FROM fact_revenue"),
            _count(conn, "SELECT COALESCE(SUM(revenue), 0) FROM fact_revenue"),
            _count(conn, "SELECT COALESCE(SUM(amount), 0) FROM fact_order"),
            _count(conn, "SELECT COALESCE(SUM(actual_amount), 0) FROM fact_collection"),
        )
    finally:
        conn.close()


def check_deterministic(conn: sqlite3.Connection, db_path: Path) -> tuple[bool, str]:
    """用同一份代码在临时目录重建一次，比对聚合指纹。"""
    with tempfile.TemporaryDirectory() as tmp:
        other = Path(tmp) / "warehouse.db"
        build(other, force=True)
        same = _fingerprint(db_path) == _fingerprint(other)
    return (same, "重建结果一致" if same else "重建结果不一致（生成器不满足可复现）")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="业务库自检")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}，请先执行 python -m app.db.init_db")
        return 2

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        results = [
            ("行数与维度", check_rows(conn)),
            ("外键完整性", check_foreign_keys(conn)),
            ("完成率区间", check_completion(conn)),
            ("订单/收入勾稽", check_order_vs_revenue(conn)),
            ("月度合计", check_monthly_sums(conn)),
            ("回款合理性", check_collection(conn)),
            ("商解目标口径", check_target_sol(conn)),
            ("可复现性", check_deterministic(conn, db_path)),
        ]
    finally:
        conn.close()

    failed = 0
    for name, (ok, detail) in results:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name:<12} {detail}")
        if not ok:
            failed += 1
    print(f"\n{len(results) - failed}/{len(results)} 项通过")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
