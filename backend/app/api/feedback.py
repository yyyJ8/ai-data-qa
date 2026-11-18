"""反馈（回复校对）接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db.app_store import AppStore
from .deps import get_store

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: int | None = None
    sql: str | None = None
    reason: str | None = Field(default=None, max_length=500)


class FeedbackUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(待处理|已处理)$")
    remark: str | None = Field(default=None, max_length=1000)


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
    updated = store.update_feedback(feedback_id, status=payload.status, remark=payload.remark)
    if not updated:
        raise HTTPException(status_code=404, detail="反馈不存在")
    return updated
