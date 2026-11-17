"""集中式配置：从 backend/.env 读取，禁止在业务代码里散落 os.environ。

约定：
- 所有键均为小写蛇形，对应 .env 中的大写键（pydantic-settings 自动映射）。
- 密钥使用 SecretStr，打印或日志中不会出现明文。
- 数据库的相对路径以 backend/ 为基准，从任何工作目录启动都指向同一文件。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
SCHEMA_FILE = BACKEND_DIR / "app" / "db" / "schema.sql"


class Settings(BaseSettings):
    """应用配置。字段默认值与 backend/.env.example 保持一致。"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 模型 ----------
    llm_base_url: str = Field(default="https://api.deepseek.com", alias="LLM_BASE_URL")
    llm_model: str = Field(default="deepseek-flash", alias="LLM_MODEL")
    llm_api_key: SecretStr = Field(default=SecretStr(""), alias="LLM_API_KEY")
    llm_thinking: bool = Field(default=True, alias="LLM_THINKING")
    llm_reasoning_effort: str = Field(default="high", alias="LLM_REASONING_EFFORT")
    llm_timeout: int = Field(default=90, ge=5, le=600, alias="LLM_TIMEOUT")

    # ---------- 数据库 ----------
    db_path: str = Field(default="data/warehouse.db", alias="DB_PATH")
    app_db_path: str = Field(default="data/app.db", alias="APP_DB_PATH")

    # ---------- SQL 保护 ----------
    sql_max_rows: int = Field(default=200, ge=1, le=5000, alias="SQL_MAX_ROWS")
    sql_timeout_ms: int = Field(default=5000, ge=100, le=60000, alias="SQL_TIMEOUT_MS")

    # ---------- 应用 ----------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---------- 派生属性 ----------
    @property
    def warehouse_path(self) -> Path:
        return self._resolve(self.db_path)

    @property
    def app_db_file(self) -> Path:
        return self._resolve(self.app_db_path)

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.get_secret_value())

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例；测试中可用 get_settings.cache_clear() 复位。"""
    return Settings()
