"""问数主链路：召回表 → 构造 Prompt → 生成 SQL → 校验 → 执行 → 整形。

对外只暴露 answer()，返回结构化结果，方便接口层与评测脚本复用。
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

from ..core.settings import Settings, get_settings
from ..llm.client import LLMClient, LLMError
from ..llm.prompts import build_messages, build_retry_messages
from ..sql import guard
from ..sql.schema import recall, render_ddl


@dataclass
class QAResult:
    question: str
    tables: list[str] = field(default_factory=list)
    sql: str | None = None
    chart: str = "none"
    explanation: str = ""
    followups: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    elapsed_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    attempts: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.sql)


def answer(
    question: str,
    *,
    history: list[dict] | None = None,
    settings: Settings | None = None,
    client: LLMClient | None = None,
    max_tokens: int = 3000,
    max_attempts: int = 2,
) -> QAResult:
    """history: 之前的对话消息（[{role, content}]），用于多轮追问。"""
    settings = settings or get_settings()
    client = client or LLMClient(settings)

    tables = recall(question)
    ddl = render_ddl(tables)
    messages = build_messages(question, ddl, history)
    result = QAResult(question=question, tables=tables)

    conn = guard.connect_readonly(settings.warehouse_path)
    try:
        allowed = guard.list_tables(conn)
        start = time.perf_counter()

        for attempt in range(1, max_attempts + 1):
            result.attempts = attempt
            try:
                payload, response = client.complete_json(messages, max_tokens=max_tokens)
            except LLMError as exc:
                result.error = str(exc)
                break

            result.prompt_tokens += response.prompt_tokens
            result.completion_tokens += response.completion_tokens
            result.sql = payload.get("sql")
            result.chart = payload.get("chart") or "table"
            result.explanation = payload.get("explanation") or ""
            followups = payload.get("followups") or []
            if isinstance(followups, list):
                result.followups = [str(item).strip() for item in followups if str(item).strip()][:3]

            if not result.sql:
                result.sql = None
                break

            try:
                query = guard.execute_readonly(
                    conn,
                    result.sql,
                    max_rows=settings.sql_max_rows,
                    timeout_ms=settings.sql_timeout_ms,
                    allowed_tables=allowed,
                )
            except (guard.SqlError, sqlite3.Error) as exc:
                result.error = str(exc)
                if attempt < max_attempts:
                    messages = build_retry_messages(messages, str(exc))
                    continue
                break

            result.error = None
            result.columns = query.columns
            result.rows = [list(row) for row in query.rows]
            if not result.followups:
                # 模型偶尔漏掉 followups，用确定性模板兜底，保证前端体验稳定
                candidates = [
                    "按经营单元拆分看看" if "经营单元" not in result.sql else "按行业拆分看看",
                    "2025年同期是多少？" if "2026" in result.sql else "各产品线同比如何？",
                ]
                result.followups = candidates[:2]
            break

        result.elapsed_ms = int((time.perf_counter() - start) * 1000)
    finally:
        conn.close()
    return result
