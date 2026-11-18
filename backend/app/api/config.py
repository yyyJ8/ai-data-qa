"""配置接口：应用配置（开场白等）与模型配置（含连通性测试）。"""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..core.settings import get_settings
from ..db.app_store import AppStore
from ..llm.client import LLMError
from ..services.model_config import build_client, load_model_config, save_model_config
from .deps import get_store

router = APIRouter(prefix="/api/config", tags=["config"])

APP_KEY = "app"
APP_DEFAULTS: dict = {
    "greeting": True,
    "greetingText": "欢迎使用智能AI问数，您可以向我咨询经营数据、报表分析相关问题。",
    "greetingQuestions": ["2026年各经营单元收入排名", "各产品线收入占比", "本月回款情况"],
    "suggestions": True,
    "hotThreshold": 3,
}


class AppConfigUpdate(BaseModel):
    greeting: bool | None = None
    greetingText: str | None = Field(default=None, max_length=200)
    greetingQuestions: list[str] | None = None
    suggestions: bool | None = None
    hotThreshold: int | None = Field(default=None, ge=1, le=100)


class ModelConfigUpdate(BaseModel):
    base_url: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=100)
    thinking: bool | None = None
    reasoning_effort: Literal["low", "medium", "high"] | None = None


@router.get("/app")
def get_app_config(store: AppStore = Depends(get_store)) -> dict:
    saved = store.get_config().get(APP_KEY, {})
    return {**APP_DEFAULTS, **saved}


@router.put("/app")
def put_app_config(payload: AppConfigUpdate, store: AppStore = Depends(get_store)) -> dict:
    saved = store.get_config().get(APP_KEY, {})
    updates = payload.model_dump(exclude_none=True)
    if "greetingQuestions" in updates:
        updates["greetingQuestions"] = [q.strip() for q in updates["greetingQuestions"] if q.strip()][:10]
    merged = {**APP_DEFAULTS, **saved, **updates}
    store.set_config({APP_KEY: merged})
    return merged


@router.get("/model")
def get_model_config(store: AppStore = Depends(get_store)) -> dict:
    return load_model_config(store, get_settings())


@router.put("/model")
def put_model_config(payload: ModelConfigUpdate, store: AppStore = Depends(get_store)) -> dict:
    return save_model_config(store, payload.model_dump(exclude_none=True), get_settings())


@router.post("/model/test")
def test_model_config(store: AppStore = Depends(get_store)) -> dict:
    """用当前生效配置发一次最小请求，确认真能连通。"""
    settings = get_settings()
    start = time.perf_counter()
    try:
        client = build_client(store, settings)
        response = client.complete(
            [{"role": "user", "content": "只回复两个字：可用"}], max_tokens=200, thinking=False
        )
    except LLMError as exc:
        return {"ok": False, "error": str(exc), "elapsed_ms": int((time.perf_counter() - start) * 1000)}

    return {
        "ok": True,
        "model": response.model,
        "latency_ms": response.elapsed_ms,
        "total_ms": int((time.perf_counter() - start) * 1000),
        "reply": response.content[:50],
    }
