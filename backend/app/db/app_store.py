"""应用元数据库（会话、消息、反馈、配置）——与业务库 warehouse.db 分离。

业务库只读，这里可写；两者互不影响，也便于单独备份。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    pinned     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role       TEXT NOT NULL,              -- user / assistant
    content    TEXT NOT NULL,
    sql        TEXT,
    chart      TEXT,
    meta       TEXT,                       -- JSON：耗时、token、召回表等
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER,
    question      TEXT NOT NULL,
    sql           TEXT,
    reason        TEXT,
    status        TEXT NOT NULL DEFAULT '待处理',
    remark        TEXT,
    corrected_sql TEXT,                       -- 人工修正后的 SQL
    promoted_at   TEXT,                       -- 写入评测集的时间
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, message_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AppStore:
    """轻量 DAO：每次调用开连接，避免跨线程复用 sqlite 连接。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # ---------- 基础 ----------
    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            # 轻量迁移：老库补列（SQLite 不支持 ADD COLUMN IF NOT EXISTS）
            for statement in (
                "ALTER TABLE feedback ADD COLUMN corrected_sql TEXT",
                "ALTER TABLE feedback ADD COLUMN promoted_at TEXT",
            ):
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError:
                    pass

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ---------- 会话 ----------
    def create_session(self, title: str) -> dict:
        now = _now()
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO sessions(title, pinned, created_at, updated_at) VALUES (?, 0, ?, ?)",
                (title, now, now),
            )
            session_id = cur.lastrowid
        return {"session_id": session_id, "title": title, "pinned": False, "created_at": now, "updated_at": now}

    def list_sessions(self, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.session_id, s.title, s.pinned, s.created_at, s.updated_at,
                       (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count,
                       (SELECT content FROM messages m WHERE m.session_id = s.session_id
                        ORDER BY message_id DESC LIMIT 1) AS preview
                FROM sessions s
                ORDER BY s.pinned DESC, s.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def update_session(self, session_id: int, title: str | None = None, pinned: bool | None = None) -> dict | None:
        fields, params = [], []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if pinned is not None:
            fields.append("pinned = ?")
            params.append(1 if pinned else 0)
        if not fields:
            return self.get_session(session_id)
        params.append(_now())
        params.append(session_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE sessions SET {', '.join(fields)}, updated_at = ? WHERE session_id = ?", params)
        return self.get_session(session_id)

    def delete_session(self, session_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        return cur.rowcount > 0

    def touch_session(self, session_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (_now(), session_id))

    # ---------- 消息 ----------
    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        sql: str | None = None,
        chart: str | None = None,
        meta: dict | None = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO messages(session_id, role, content, sql, chart, meta, created_at) VALUES (?,?,?,?,?,?,?)",
                (session_id, role, content, sql, chart, json.dumps(meta or {}, ensure_ascii=False), _now()),
            )
            message_id = cur.lastrowid
            conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (_now(), session_id))
        return message_id

    def list_messages(self, session_id: int) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT message_id, role, content, sql, chart, meta, created_at "
                "FROM messages WHERE session_id = ? ORDER BY message_id",
                (session_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["meta"] = json.loads(item["meta"] or "{}")
            result.append(item)
        return result

    # ---------- 反馈 ----------
    def add_feedback(self, question: str, session_id: int | None = None, sql: str | None = None, reason: str | None = None) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO feedback(session_id, question, sql, reason, status, created_at) VALUES (?,?,?,?,?,?)",
                (session_id, question, sql, reason, "待处理", _now()),
            )
            return cur.lastrowid

    def list_feedback(self, status: str | None = None) -> list[dict]:
        sql = "SELECT * FROM feedback"
        params: tuple = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY feedback_id DESC"
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def update_feedback(
        self,
        feedback_id: int,
        status: str | None = None,
        remark: str | None = None,
        corrected_sql: str | None = None,
    ) -> dict | None:
        fields, params = [], []
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if remark is not None:
            fields.append("remark = ?")
            params.append(remark)
        if corrected_sql is not None:
            fields.append("corrected_sql = ?")
            params.append(corrected_sql)
        if fields:
            params.append(feedback_id)
            with self.connect() as conn:
                conn.execute(f"UPDATE feedback SET {', '.join(fields)} WHERE feedback_id = ?", params)
        return self.get_feedback(feedback_id)

    def get_feedback(self, feedback_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM feedback WHERE feedback_id = ?", (feedback_id,)).fetchone()
        return dict(row) if row else None

    def mark_promoted(self, feedback_id: int) -> dict | None:
        with self.connect() as conn:
            conn.execute("UPDATE feedback SET promoted_at = ? WHERE feedback_id = ?", (_now(), feedback_id))
        return self.get_feedback(feedback_id)

    # ---------- 配置 ----------
    def get_config(self) -> dict:
        with self.connect() as conn:
            rows = conn.execute("SELECT key, value FROM app_config").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def set_config(self, values: dict) -> dict:
        with self.connect() as conn:
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO app_config(key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(value, ensure_ascii=False)),
                )
        return self.get_config()
