"""评测脚本：跑完整评测集，产出基线分数。

判定方式：把模型 SQL 与标准 SQL 各执行一次，按"行数一致 + 逐值相等（数值容差 0.01）"比对。
- exact：完全一致（含行序）
- unordered：值一致但行序不同（排名类问题算错，单独统计）
- fail：SQL 出错、返回空或数值不一致

用法（backend/ 下）：
    .venv\\Scripts\\python.exe scripts/eval.py
    .venv\\Scripts\\python.exe scripts/eval.py --limit 5 --no-thinking
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import get_settings  # noqa: E402
from app.services.qa import answer  # noqa: E402
from app.sql import guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "samples" / "eval_cases.jsonl"
REPORT_DIR = ROOT / "samples" / "reports"


def normalize(value):
    if value is None:
        return None
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, int):
        return value
    return str(value).strip()


def row_equal(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        x, y = normalize(x), normalize(y)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            if abs(float(x) - float(y)) > 0.01:
                return False
        elif x != y:
            return False
    return True


def _numerics(row: list) -> list[float]:
    return [float(normalize(v)) for v in row if isinstance(v, (int, float))]


def contains_values(ref_row: list, got_row: list) -> bool:
    """标准答案的每个数值都能在模型结果行中找到（容忍模型多出派生列）。"""
    got = _numerics(got_row)
    for value in _numerics(ref_row):
        if not any(abs(value - g) <= 0.01 for g in got):
            return False
    return True


def compare(ref_rows: list, got_rows: list) -> str:
    if len(ref_rows) != len(got_rows):
        return "fail"
    if all(row_equal(r, g) for r, g in zip(ref_rows, got_rows)):
        return "exact"
    if all(contains_values(r, g) for r, g in zip(ref_rows, got_rows)):
        return "value"
    ref_sorted = sorted(ref_rows, key=lambda r: [str(normalize(v)) for v in r])
    got_sorted = sorted(got_rows, key=lambda r: [str(normalize(v)) for v in r])
    if all(row_equal(r, g) for r, g in zip(ref_sorted, got_sorted)):
        return "unordered"
    return "fail"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="评测集跑分")
    parser.add_argument("--cases", default=str(CASES))
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条")
    parser.add_argument("--no-thinking", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=1500)
    parser.add_argument("--verbose", action="store_true", help="打印每条结果")
    args = parser.parse_args(argv)

    settings = get_settings()
    cases = [json.loads(line) for line in Path(args.cases).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        cases = cases[: args.limit]

    conn = guard.connect_readonly(settings.warehouse_path)
    results = []
    started = time.time()
    try:
        allowed = guard.list_tables(conn)
        for index, case in enumerate(cases, start=1):
            ref = guard.execute_readonly(
                conn, case["sql"], max_rows=1000, allowed_tables=allowed
            )
            result = answer(case["question"], settings=settings, max_tokens=args.max_tokens)

            outcome, detail = "fail", ""
            if result.error:
                detail = f"error: {result.error[:80]}"
            elif not result.sql:
                detail = f"no_sql: {result.explanation[:60]}"
            elif not result.rows:
                detail = "empty_result"
            else:
                outcome = compare([list(r) for r in ref.rows], result.rows)
                if outcome != "exact":
                    detail = f"ref={len(ref.rows)}行 got={len(result.rows)}行"

            results.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "outcome": outcome,
                    "detail": detail,
                    "sql": result.sql,
                    "ref_sql": case["sql"],
                    "elapsed_ms": result.elapsed_ms,
                    "tokens": result.prompt_tokens + result.completion_tokens,
                }
            )
            mark = {"exact": "PASS", "value": "VALUE", "unordered": "ORDER", "fail": "FAIL"}[outcome]
            if args.verbose or outcome == "fail":
                print(f"[{mark}] {case['id']} {case['question']}  {detail}")
    finally:
        conn.close()

    total = len(results)
    exact = sum(1 for r in results if r["outcome"] == "exact")
    value = sum(1 for r in results if r["outcome"] == "value")
    unordered = sum(1 for r in results if r["outcome"] == "unordered")
    executable = sum(1 for r in results if r["sql"])
    elapsed = time.time() - started

    print("\n" + "=" * 60)
    print(f"用例数        : {total}")
    print(f"SQL 可执行率  : {executable}/{total} = {executable / total * 100:.1f}%")
    print(f"严格正确（含行序与列）: {exact}/{total} = {exact / total * 100:.1f}%")
    print(f"数值命中（允许多余派生列）: {(exact + value)}/{total} = {(exact + value) / total * 100:.1f}%")
    print(f"行序不一致    : {unordered}")
    print(f"总耗时        : {elapsed:.1f}s（均 {elapsed / total:.1f}s/条）")
    print("=" * 60)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORT_DIR / f"report-{stamp}.json"
    report_path.write_text(
        json.dumps(
            {
                "generated_at": stamp,
                "model": settings.llm_model,
                "total": total,
                "exact": exact,
                "value": value,
                "unordered": unordered,
                "executable": executable,
                "elapsed_s": round(elapsed, 1),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"报告: {report_path}")
    return 0 if exact == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
