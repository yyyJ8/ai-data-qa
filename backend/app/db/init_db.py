"""业务库初始化：建表 + 灌种子数据（幂等）。

用法：
    python -m app.db.init_db                # 默认 backend/data/warehouse.db
    python -m app.db.init_db --force        # 删库重建
    python -m app.db.init_db --db D:/x.db   # 指定路径
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from .seed import seed_all

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "warehouse.db"


def build(db_path: Path, force: bool = False) -> dict[str, int]:
    """建库并灌数；已存在且非空时直接返回现有行数。"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if force and db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        existing = conn.execute("SELECT COUNT(*) FROM dim_unit").fetchone()[0]
        if existing == 0:
            counts = seed_all(conn)
        else:
            counts = table_counts(conn)
        conn.commit()
        return counts
    finally:
        conn.close()


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [
        "dim_unit", "dim_industry", "dim_product_line", "dim_product", "dim_customer",
        "fact_target", "fact_revenue", "fact_order", "fact_collection", "fact_ppl",
    ]
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="初始化业务库（建表 + 种子数据）")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="数据库文件路径")
    parser.add_argument("--force", action="store_true", help="删除已有数据库后重建")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    counts = build(db_path, force=args.force)

    print(f"数据库: {db_path}")
    print(f"状态  : {'重建' if args.force else '就绪'}")
    for name, count in counts.items():
        print(f"  {name:<18} {count:>7}")
    print(f"合计  : {sum(counts.values()):>7} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
