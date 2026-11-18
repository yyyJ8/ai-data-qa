"""模型配置的读取、保存与客户端构造。

设计取舍：**API Key 不入库**。密钥只从 `.env` 读取，前端只能看到掩码；
库里保存的是"用哪个模型、是否开思考、思考强度、base_url"这类可公开的配置。
这样即使元数据库泄露，也不会连带泄露密钥。
"""

from __future__ import annotations

from ..core.settings import Settings
from ..db.app_store import AppStore
from ..llm.client import LLMClient

CONFIG_KEY = "model"


def mask_key(settings: Settings) -> str:
    secret = settings.llm_api_key.get_secret_value()
    if not secret:
        return ""
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}****{secret[-4:]}"


def load_model_config(store: AppStore, settings: Settings) -> dict:
    saved = store.get_config().get(CONFIG_KEY, {})
    return {
        "base_url": saved.get("base_url") or settings.llm_base_url,
        "model": saved.get("model") or settings.llm_model,
        "thinking": saved.get("thinking", settings.llm_thinking),
        "reasoning_effort": saved.get("reasoning_effort") or settings.llm_reasoning_effort,
        "api_key_masked": mask_key(settings),
        "configured": settings.llm_configured,
    }


def save_model_config(store: AppStore, payload: dict, settings: Settings) -> dict:
    current = load_model_config(store, settings)
    merged = {
        "base_url": payload.get("base_url") or current["base_url"],
        "model": payload.get("model") or current["model"],
        "thinking": payload.get("thinking", current["thinking"]),
        "reasoning_effort": payload.get("reasoning_effort") or current["reasoning_effort"],
    }
    store.set_config({CONFIG_KEY: merged})
    return load_model_config(store, settings)


def build_client(store: AppStore, settings: Settings) -> LLMClient:
    cfg = load_model_config(store, settings)
    return LLMClient(
        settings,
        model=cfg["model"],
        base_url=cfg["base_url"],
        thinking=cfg["thinking"],
        reasoning_effort=cfg["reasoning_effort"],
    )
