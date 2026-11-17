"""问数接口：SSE 分片返回「发现 → 表格 → 图表 → 洞察 → 结束」。

事件序列（正常）：
    session → stage(1 选表) → stage(2 SQL) → stage(3 执行)
    → table → chart → insight → done

失败时：error（带 message），随后仍发 done，便于前端收尾。
"""

from __future__ import annotations

import json
import logging

import anyio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..db.app_store import AppStore
from ..services.qa import QAResult
from ..services.qa import answer as run_answer
from ..sql.schema import recall
from .deps import get_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: int | None = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(payload: ChatRequest, store: AppStore = Depends(get_store)) -> StreamingResponse:
    question = payload.question.strip()
    session = store.get_session(payload.session_id) if payload.session_id else None
    if session is None:
        session = store.create_session(question[:20] or "新对话")
    session_id = session["session_id"]

    store.add_message(session_id, "user", question)
    tables = recall(question)

    async def event_stream():
        yield _sse("session", {"session_id": session_id, "title": session["title"]})
        yield _sse("stage", {"step": 1, "title": "选择数据表", "detail": "、".join(tables)})

        try:
            result: QAResult = await anyio.to_thread.run_sync(run_answer, question)
        except Exception as exc:  # noqa: BLE001
            logger.exception("问数失败")
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
            yield _sse("done", {"session_id": session_id})
            return

        if result.error:
            yield _sse("error", {"message": result.error})
            store.add_message(
                session_id, "assistant", f"查询失败：{result.error}", sql=result.sql,
                meta={"tables": tables, "elapsed_ms": result.elapsed_ms},
            )
            yield _sse("done", {"session_id": session_id, "elapsed_ms": result.elapsed_ms})
            return

        yield _sse("stage", {"step": 2, "title": "生成 SQL", "detail": result.sql})
        yield _sse("stage", {"step": 3, "title": "执行查询", "detail": f"命中 {len(result.rows)} 行"})
        yield _sse("table", {"columns": result.columns, "rows": result.rows, "row_limit": 200})
        yield _sse("chart", {"type": result.chart})
        if result.explanation:
            yield _sse("insight", {"text": result.explanation})

        store.add_message(
            session_id,
            "assistant",
            result.explanation or "已完成查询",
            sql=result.sql,
            chart=result.chart,
            meta={
                "tables": tables,
                "elapsed_ms": result.elapsed_ms,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "attempts": result.attempts,
                "rows": len(result.rows),
            },
        )
        yield _sse(
            "done",
            {
                "session_id": session_id,
                "sql": result.sql,
                "elapsed_ms": result.elapsed_ms,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
