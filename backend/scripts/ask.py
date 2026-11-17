"""命令行问数：跑通"问题 → SQL → 结果"的最小闭环。

用法（backend/ 下）：
    .venv\\Scripts\\python.exe scripts/ask.py "2026年各经营单元收入排名前十"
    .venv\\Scripts\\python.exe scripts/ask.py "..." --no-thinking
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.qa import answer  # noqa: E402


def render_table(columns: list[str], rows: list[list], limit: int = 20) -> str:
    if not columns:
        return "(无结果)"
    widths = [len(c) for c in columns]
    for row in rows[:limit]:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(str(value)))

    def line(values):
        return " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(values))

    out = [line(columns), "-+-".join("-" * w for w in widths)]
    out += [line(row) for row in rows[:limit]]
    if len(rows) > limit:
        out.append(f"... 共 {len(rows)} 行，仅显示前 {limit} 行")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="问数命令行")
    parser.add_argument("question")
    parser.add_argument("--no-thinking", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=3000)
    args = parser.parse_args(argv)

    result = answer(args.question, max_tokens=args.max_tokens)

    print(f"问题     : {result.question}")
    print(f"召回表   : {', '.join(result.tables)}")
    print(f"尝试次数 : {result.attempts}")
    print(f"耗时     : {result.elapsed_ms} ms（token: {result.prompt_tokens}+{result.completion_tokens}）")
    if result.error:
        print(f"错误     : {result.error}")
        if result.sql:
            print(f"失败 SQL : {result.sql}")
        return 1
    if not result.sql:
        print(f"未生成 SQL: {result.explanation}")
        return 2

    print(f"SQL      : {result.sql}")
    print(f"图表建议 : {result.chart}")
    print(f"说明     : {result.explanation}")
    print()
    print(render_table(result.columns, result.rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
