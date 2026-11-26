"""评测语料可执行性检查。

逐条执行 samples/eval_cases.jsonl 里的标准 SQL，确认：
1. JSON 结构合法、字段齐全；
2. SQL 能在业务库上执行；
3. 返回行数大于 0。

用法：
    python samples/check_cases.py
    python samples/check_cases.py --db backend/data/warehouse.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "warehouse.db"
CASES = ROOT / "samples" / "eval_cases.jsonl"
REQUIRED = {"id", "question", "sql", "tags"}


def load_cases(path: Path) -> list[dict]:
    cases = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"第 {lineno} 行 JSON 解析失败: {exc}") from exc
        missing = REQUIRED - case.keys()
        if missing:
            raise SystemExit(f"第 {lineno} 行缺少字段: {sorted(missing)}")
        cases.append(case)
    return cases


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        getattr(sys.stdout, "reconfigure")(encoding="utf-8")

    parser = argparse.ArgumentParser(description="评测语料可执行性检查")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--cases", default=str(CASES))
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}，请先执行 python -m app.db.init_db")
        return 2

    cases = load_cases(Path(args.cases))
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    failures = 0
    ids = set()
    try:
        for case in cases:
            if case["id"] in ids:
                print(f"[FAIL] {case['id']} id 重复")
                failures += 1
                continue
            ids.add(case["id"])
            try:
                rows = conn.execute(case["sql"]).fetchall()
            except sqlite3.Error as exc:
                print(f"[FAIL] {case['id']} SQL 执行失败: {exc}")
                failures += 1
                continue
            if not rows:
                print(f"[FAIL] {case['id']} 返回 0 行: {case['question']}")
                failures += 1
                continue
            print(f"[PASS] {case['id']} rows={len(rows):<3} {case['question']}")
    finally:
        conn.close()

    print(f"\n{len(cases) - failures}/{len(cases)} 条通过")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
