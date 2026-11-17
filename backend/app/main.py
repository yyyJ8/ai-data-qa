"""FastAPI 应用入口。

已接入：健康检查、问数（SSE）、会话管理。配置/数据/反馈接口随后接入。
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI

from .api import chat, sessions
from .core.settings import SCHEMA_FILE, Settings, get_settings
from .db.app_store import AppStore


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    AppStore(settings.app_db_file).init()
    yield


app = FastAPI(
    title="AI问数",
    description="企业级销售经管数据问答平台（text2sql）",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(chat.router)
app.include_router(sessions.router)


def _warehouse_status(settings: Settings) -> dict:
    path = settings.warehouse_path
    if not path.exists():
        return {"path": str(path), "exists": False, "tables": 0}
    with closing(sqlite3.connect(path)) as conn:
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
    return {"path": str(path), "exists": True, "tables": tables}


@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "version": app.version,
        "llm": {
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
            "configured": settings.llm_configured,
            "thinking": settings.llm_thinking,
        },
        "warehouse": _warehouse_status(settings),
        "schema": SCHEMA_FILE.exists(),
    }
