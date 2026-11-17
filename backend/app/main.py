"""FastAPI 应用入口。

当前只提供健康检查；问答、会话、配置等接口在 M3 逐步接入。
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI

from .core.settings import SCHEMA_FILE, Settings, get_settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(get_settings())
    yield


app = FastAPI(
    title="AI问数",
    description="企业级销售经管数据问答平台（text2sql）",
    version="0.2.0",
    lifespan=lifespan,
)


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
