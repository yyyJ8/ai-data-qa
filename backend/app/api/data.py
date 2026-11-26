"""数据接口：台账分页浏览与导出 Excel。

安全约定：
- 表名必须在只读库的真实表/视图清单里；
- 排序字段必须属于该表；
- 过滤值只做字符串字面量转义后内联（不允许用户拼接 SQL 片段）。
"""

from __future__ import annotations

import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from ..core.settings import get_settings
from ..sql import guard

router = APIRouter(prefix="/api/data", tags=["data"])

MAX_EXPORT_ROWS = 5000


def _lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class _TableInfo:
    def __init__(self, conn, table: str) -> None:
        self.table = table
        self.columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        self.types = {r[1]: (r[2] or "").upper() for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        self.text_columns = [c for c, t in self.types.items() if "CHAR" in t or "TEXT" in t or "CLOB" in t]


def _open(table: str):
    settings = get_settings()
    conn = guard.connect_readonly(settings.warehouse_path)
    allowed = set(guard.list_tables(conn))
    if table not in allowed:
        conn.close()
        raise HTTPException(status_code=404, detail=f"表不存在: {table}")
    return conn, allowed, _TableInfo(conn, table)


def _build_query(info: _TableInfo, q: str | None, sort: str | None, order: str, limit: int, offset: int) -> str:
    where = ""
    if q and info.text_columns:
        pattern = _lit(f"%{q}%")
        where = "WHERE " + " OR ".join(f"{c} LIKE {pattern}" for c in info.text_columns)

    order_by = ""
    if sort:
        if sort not in info.columns:
            raise HTTPException(status_code=400, detail=f"排序字段不存在: {sort}")
        direction = "DESC" if order.lower() == "desc" else "ASC"
        order_by = f"ORDER BY {sort} {direction}"

    return f"SELECT * FROM {info.table} {where} {order_by} LIMIT {limit} OFFSET {offset}".strip()


@router.get("/{table}")
def read_table(
    table: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str | None = None,
    order: str = "asc",
    q: str | None = None,
) -> dict:
    conn, allowed, info = _open(table)
    try:
        where = ""
        if q and info.text_columns:
            pattern = _lit(f"%{q}%")
            where = "WHERE " + " OR ".join(f"{c} LIKE {pattern}" for c in info.text_columns)

        total = guard.execute_readonly(
            conn, f"SELECT COUNT(*) AS n FROM {info.table} {where}".strip(), max_rows=1, allowed_tables=allowed
        ).rows[0][0]

        sql = _build_query(info, q, sort, order, page_size, (page - 1) * page_size)
        result = guard.execute_readonly(conn, sql, max_rows=page_size, allowed_tables=allowed)
        return {
            "table": table,
            "columns": info.columns,
            "rows": [list(r) for r in result.rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        conn.close()


@router.get("/{table}/export")
def export_table(
    table: str,
    sort: str | None = None,
    order: str = "asc",
    q: str | None = None,
) -> StreamingResponse:
    conn, allowed, info = _open(table)
    try:
        sql = _build_query(info, q, sort, order, MAX_EXPORT_ROWS, 0)
        result = guard.execute_readonly(conn, sql, max_rows=MAX_EXPORT_ROWS, allowed_tables=allowed)
        columns = result.columns
        rows = [list(r) for r in result.rows]
    finally:
        conn.close()

    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:  # openpyxl 新建工作簿必有默认表，这里只为类型收窄
        raise HTTPException(status_code=500, detail="无法创建工作表")
    sheet.title = table[:30]
    sheet.append(columns)
    for row in rows:
        sheet.append(row)

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    filename = f"{table}.xlsx"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
