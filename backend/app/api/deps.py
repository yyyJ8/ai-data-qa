"""API 依赖：把 settings 里的路径注入成 store。"""

from __future__ import annotations

from ..core.settings import get_settings
from ..db.app_store import AppStore


def get_store() -> AppStore:
    return AppStore(get_settings().app_db_file)
