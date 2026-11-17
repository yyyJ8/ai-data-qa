"""LLM 连通性检查：验证 Key、模型名与思考开关是否可用。

用法（在 backend/ 下）：
    .venv\\Scripts\\python.exe scripts/check_llm.py
    .venv\\Scripts\\python.exe scripts/check_llm.py --no-thinking
    .venv\\Scripts\\python.exe scripts/check_llm.py --json --max-tokens 800

退出码：0 正常；2 未配置 Key；3 请求失败；4 返回空内容（通常是 max_tokens 被思考耗尽）。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import OpenAI  # noqa: E402

from app.core.settings import get_settings  # noqa: E402

JSON_PROMPT = (
    "表 fact_revenue(month TEXT, unit_id INTEGER, revenue INTEGER)。"
    "问：2026年各月收入。只输出 JSON：{\"sql\": \"...\"}"
)
PLAIN_PROMPT = "只回复两个字：可用"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    parser = argparse.ArgumentParser(description="LLM 连通性检查")
    parser.add_argument("--thinking", dest="thinking", action="store_true", default=settings.llm_thinking)
    parser.add_argument("--no-thinking", dest="thinking", action="store_false")
    parser.add_argument("--json", action="store_true", help="用 text2sql 场景的 JSON 提示词")
    parser.add_argument("--max-tokens", type=int, default=800)
    args = parser.parse_args(argv)

    if not settings.llm_configured:
        print("LLM_API_KEY 未配置，请在 backend/.env 中填写")
        return 2

    client = OpenAI(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout,
    )

    extra_body: dict = {"thinking": {"type": "enabled" if args.thinking else "disabled"}}
    if args.thinking:
        extra_body["reasoning_effort"] = settings.llm_reasoning_effort

    prompt = JSON_PROMPT if args.json else PLAIN_PROMPT
    print(f"model={settings.llm_model} thinking={args.thinking} max_tokens={args.max_tokens}")

    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=args.max_tokens,
            extra_body=extra_body,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"请求失败: {type(exc).__name__}: {exc}")
        return 3
    elapsed = time.perf_counter() - start

    message = resp.choices[0].message
    content = (message.content or "").strip()
    reasoning = getattr(message, "reasoning_content", None) or (message.model_extra or {}).get("reasoning_content")
    usage = resp.usage
    details = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = getattr(details, "reasoning_tokens", "?") if details else "?"

    print(f"耗时      : {elapsed:.2f}s")
    print(f"模型回显  : {resp.model}")
    print(f"token     : prompt={usage.prompt_tokens} completion={usage.completion_tokens}"
          f" reasoning={reasoning_tokens}")
    print(f"思考内容  : {'有' if reasoning else '无'}")
    print(f"输出      : {content[:200]!r}")

    if not content:
        print("\n返回内容为空 —— 通常是 max_tokens 被思考 token 占满，请调大 --max-tokens")
        return 4

    if args.json:
        ok = content.startswith("{") and content.endswith("}")
        print(f"JSON 形态 : {'合法' if ok else '不合法'}")
        if not ok:
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
