"""反馈（回复校对）接口，含"修正 SQL 回灌评测集"。"""

from __future__ import annotations

import json
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.settings import get_settings
from ..db.app_store import AppStore
from ..sql import guard
from .deps import get_store

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

CASE_ID_RE = re.compile(r"^q(\d+)$")


class FeedbackCreate(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: int | None = None
    sql: str | None = None
    reason: str | None = Field(default=None, max_length=500)


class FeedbackUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(待处理|已处理)$")
    remark: str | None = Field(default=None, max_length=1000)
    corrected_sql: str | None = Field(default=None, max_length=4000)


@router.get("")
def list_feedback(status: str | None = None, store: AppStore = Depends(get_store)) -> list[dict]:
    return store.list_feedback(status=status)


@router.post("", status_code=201)
def create_feedback(payload: FeedbackCreate, store: AppStore = Depends(get_store)) -> dict:
    feedback_id = store.add_feedback(
        payload.question, session_id=payload.session_id, sql=payload.sql, reason=payload.reason
    )
    return {"feedback_id": feedback_id}


@router.patch("/{feedback_id}")
def update_feedback(feedback_id: int, payload: FeedbackUpdate, store: AppStore = Depends(get_store)) -> dict:
    updated = store.update_feedback(
        feedback_id,
        status=payload.status,
        remark=payload.remark,
        corrected_sql=payload.corrected_sql,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="反馈不存在")
    return updated


def _next_case_id(questions: list[dict]) -> str:
    numbers = [0]
    for case in questions:
        match = CASE_ID_RE.match(str(case.get("id", "")))
        if match:
            numbers.append(int(match.group(1)))
    return f"q{max(numbers) + 1:02d}"


@router.post("/{feedback_id}/promote")
def promote_feedback(feedback_id: int, store: AppStore = Depends(get_store)) -> dict:
    """把校对后的 SQL 作为新的评测用例写入 samples/eval_cases.jsonl。

    写入前必须能真实执行：避免把不可用的 SQL 混进评测集，污染后续打分。
    """
    item = store.get_feedback(feedback_id)
    if not item:
        raise HTTPException(status_code=404, detail="反馈不存在")
    if item.get("promoted_at"):
        raise HTTPException(status_code=409, detail="该反馈已写入评测集")

    sql = (item.get("corrected_sql") or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="请先填写修正后的 SQL")

    settings = get_settings()
    conn = guard.connect_readonly(settings.warehouse_path)
    try:
        allowed = guard.list_tables(conn)
        result = guard.execute_readonly(conn, sql, max_rows=200, allowed_tables=allowed)
    except (guard.SqlError, sqlite3.Error) as exc:
        raise HTTPException(status_code=400, detail=f"SQL 不可执行: {exc}") from exc
    finally:
        conn.close()

    if not result.rows:
        raise HTTPException(status_code=400, detail="SQL 可执行但返回 0 行，不能作为评测用例")

    path = settings.eval_cases_file
    cases: list[dict] = []
    if path.exists():
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    question = item["question"].strip()
    if any(case.get("question", "").strip() == question for case in cases):
        raise HTTPException(status_code=409, detail="评测集已存在相同问题")

    case = {
        "id": _next_case_id(cases),
        "question": question,
        "sql": sql,
        "tags": ["from_feedback"],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    store.mark_promoted(feedback_id)
    return {"case_id": case["id"], "question": question, "rows": len(result.rows), "file": str(path)}
