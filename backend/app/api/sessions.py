"""会话接口：列表、详情、改名/置顶、删除。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db.app_store import AppStore
from .deps import get_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    title: str = Field(default="新对话", max_length=100)


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    pinned: bool | None = None


@router.get("")
def list_sessions(limit: int = 50, store: AppStore = Depends(get_store)) -> list[dict]:
    return store.list_sessions(limit=limit)


@router.post("", status_code=201)
def create_session(payload: SessionCreate, store: AppStore = Depends(get_store)) -> dict:
    return store.create_session(payload.title)


@router.get("/{session_id}")
def get_session(session_id: int, store: AppStore = Depends(get_store)) -> dict:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session["messages"] = store.list_messages(session_id)
    return session


@router.patch("/{session_id}")
def update_session(session_id: int, payload: SessionUpdate, store: AppStore = Depends(get_store)) -> dict:
    session = store.update_session(session_id, title=payload.title, pinned=payload.pinned)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, store: AppStore = Depends(get_store)) -> None:
    if not store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
