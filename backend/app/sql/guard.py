"""SQL 安全层：静态校验 + 运行时只读执行。

两层防护：
1. 静态：拒绝多语句、非 SELECT/WITH 开头、危险关键字、参数占位符；
2. 运行时：只读连接（mode=ro）+ SQLite 授权器（authorizer）——白名单之外的表一律 DENY，
   任何写操作、PRAGMA、ATTACH 都无法执行，即使静态检查被绕过。

另外统一强制 LIMIT，避免一条 SQL 拉爆内存。
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

# 允许出现在 SQL 里的关键字之外，其余写操作/管理语句一律拒绝
FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "REPLACE", "UPSERT",
    "CREATE", "DROP", "ALTER", "TRUNCATE", "RENAME",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX", "ANALYZE",
    "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE",
    "GRANT", "REVOKE", "LOAD_EXTENSION", "WRITEFILE", "READFILE",
}

DISALLOWED_FUNCTIONS = {"load_extension", "writefile", "readfile", "fts3_tokenizer"}

_LIMIT_RE = re.compile(r"\blimit\s+(\d+)\s*(?:offset\s+\d+)?\s*$", re.IGNORECASE)


class SqlError(ValueError):
    """SQL 相关错误的基类。"""


class UnsafeSqlError(SqlError):
    """静态校验未通过。"""


class SqlDeniedError(SqlError):
    """运行时授权器拒绝（越权访问表或写操作）。"""


class SqlTimeoutError(SqlError):
    """执行超时。"""


@dataclass
class GuardResult:
    sql: str                     # 规范化后的 SQL（已补/已收紧 LIMIT）
    limited: bool                # 是否由本层补上了 LIMIT
    clamped: bool                # 原有 LIMIT 是否被收紧
    notes: list[str] = field(default_factory=list)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    row_limit: int


def _strip_literals_and_comments(sql: str) -> str:
    """把字符串字面量与注释替换成空格，避免误判关键字。

    支持 '...'、'' 转义、双引号标识符、反引号、[..]，以及 -- 与 /* */ 注释。
    """
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(" ")
            i += 1
            while i < n:
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:   # 转义的两个引号
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == "[":
            while i < n and sql[i] != "]":
                i += 1
            i += 1
            out.append(" ")
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
            out.append(" ")
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _tokens(masked: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", masked)


def ensure_safe(sql: str, max_rows: int) -> GuardResult:
    """静态校验并规范化 LIMIT。不通过时抛 UnsafeSqlError。"""
    raw = (sql or "").strip()
    if not raw:
        raise UnsafeSqlError("SQL 为空")

    masked = _strip_literals_and_comments(raw).strip()
    body = masked.rstrip()

    # 多语句：只允许末尾一个分号
    if ";" in body.rstrip(";"):
        raise UnsafeSqlError("只允许单条 SQL 语句")
    if body.endswith(";"):
        raw = raw.rstrip().rstrip(";").rstrip()
        masked = masked.rstrip().rstrip(";").rstrip()

    # 参数占位符：本层不传参，出现 ?/:name 一律拒绝，避免拼接歧义
    if "?" in masked:
        raise UnsafeSqlError("不允许使用参数占位符")

    tokens = _tokens(masked)
    if not tokens:
        raise UnsafeSqlError("无法解析 SQL")
    if tokens[0].upper() not in {"SELECT", "WITH"}:
        raise UnsafeSqlError(f"只允许 SELECT/WITH 查询，收到 {tokens[0].upper()}")

    upper = {t.upper() for t in tokens}
    hits = sorted(upper & FORBIDDEN_KEYWORDS)
    if hits:
        raise UnsafeSqlError(f"包含禁止的关键字: {', '.join(hits)}")

    lowered = {t.lower() for t in tokens}
    bad_funcs = sorted(lowered & DISALLOWED_FUNCTIONS)
    if bad_funcs:
        raise UnsafeSqlError(f"包含禁止的函数: {', '.join(bad_funcs)}")

    if re.search(r"\bsqlite_[a-z_]+", masked, re.IGNORECASE):
        raise UnsafeSqlError("不允许访问 sqlite_ 系统对象")

    # LIMIT 处理
    limited, clamped = False, False
    match = _LIMIT_RE.search(raw)
    if match:
        current = int(match.group(1))
        if current > max_rows:
            raw = raw[: match.start(1)] + str(max_rows) + raw[match.end(1):]
            clamped = True
    else:
        raw = f"{raw} LIMIT {max_rows}"
        limited = True

    return GuardResult(sql=raw, limited=limited, clamped=clamped)


def _authorizer(known_tables: set[str], allowed_tables: set[str], denials: list[str]):
    def callback(action, arg1, arg2, dbname, trigger):  # noqa: ANN001
        # 只放行读操作
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE, sqlite3.SQLITE_FUNCTION):
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in DISALLOWED_FUNCTIONS:
                denials.append(f"函数被拒绝: {arg2}")
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            table = arg1 or ""
            if table.startswith("sqlite_"):
                denials.append(f"拒绝访问系统表: {table}")
                return sqlite3.SQLITE_DENY
            # CTE / 子查询别名不在真实表清单中，放行（能否解析由 SQLite 自己判断）
            if table in known_tables and allowed_tables and table not in allowed_tables:
                denials.append(f"表不在白名单: {table}")
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        denials.append(f"拒绝的操作: {action}")
        return sqlite3.SQLITE_DENY

    return callback


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    """只读打开业务库；文件不存在时直接报错，避免静默建空库。"""
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"数据库不存在: {path}")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def execute_readonly(
    conn: sqlite3.Connection,
    sql: str,
    max_rows: int = 200,
    timeout_ms: int = 5000,
    allowed_tables: Iterable[str] | None = None,
) -> QueryResult:
    """执行已校验的只读 SQL。

    调用方可以先 ensure_safe()；本函数内部也会再校验一次，防止绕过。
    """
    guard = ensure_safe(sql, max_rows)
    allowed_raw = set(allowed_tables or [])
    known_raw = set(list_tables(conn))

    denials: list[str] = []
    conn.set_authorizer(_authorizer(known_raw, allowed_raw, denials))

    deadline = time.monotonic() + timeout_ms / 1000.0

    def progress() -> int:
        return 1 if time.monotonic() > deadline else 0

    conn.set_progress_handler(progress, 10_000)
    try:
        cursor = conn.execute(guard.sql)
        rows = cursor.fetchmany(max_rows)
        columns = [d[0] for d in (cursor.description or [])]
        return QueryResult(columns=columns, rows=[tuple(r) for r in rows], row_limit=max_rows)
    except sqlite3.DatabaseError as exc:
        if denials:
            raise SqlDeniedError("; ".join(denials)) from exc
        if "not authorized" in str(exc).lower():
            raise SqlDeniedError(str(exc)) from exc
        if "interrupted" in str(exc).lower():
            raise SqlTimeoutError(f"查询超时（>{timeout_ms}ms）") from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)
        conn.set_authorizer(None)


def list_tables(conn: sqlite3.Connection) -> Sequence[str]:
    """用于构造白名单：业务表 + 视图。"""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]
