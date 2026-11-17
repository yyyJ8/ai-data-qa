"""Prompt 构造。

约定：模型只输出 JSON，解析失败由调用方重试；口径与语法规则写在 system 里，
避免每次请求都重复解释业务背景。
"""

from __future__ import annotations

SYSTEM_PROMPT = """你是企业销售经管数据的 text2sql 助手。根据用户问题与给定的表结构，生成一条 SQLite 查询。

硬性规则：
1. 只输出一个 JSON 对象，不要 Markdown 代码块，不要解释性文字。
   {"sql": "...", "chart": "bar|line|pie|table|none", "explanation": "一句话说明"}
2. 只生成单条只读 SELECT，禁止任何写操作、PRAGMA、ATTACH；不要以分号结尾。
3. 金额单位是万元，不要做单位换算；不要自己加 LIMIT，系统会统一处理。
4. 时间字段类型：year 是整数（写 year = 2026，不要加引号）；
   month 是文本 'YYYY-MM'，按年过滤用 substr(month,1,4)='2026'；
   sign_date / expected_sign_date 是文本 'YYYY-MM-DD'。
5. 同比需要同时取 2025 与 2026 两年数据；完成率 = 收入 / 商业目标 * 100。
6. 维度值用中文原文匹配，例如 unit_name='北京代表处'、line_name='通用计算'。
7. 输出列请用中文别名，例如 AS 经营单元、AS 收入额；聚合结果按需要的顺序排序。
8. 问题无法用给定表回答时，输出 {"sql": null, "chart": "none", "explanation": "缺少什么数据"}。
9. 不要输出 SELECT *，只选需要的列。
10. 涉及"排名/最高/最低/TopN"必须显式 ORDER BY，涉及"占比"要给出百分比列。"""


FEW_SHOTS: list[tuple[str, str]] = [
    (
        "2026年各经营单元收入排名前十",
        '{"sql": "SELECT u.unit_name AS 经营单元, SUM(r.revenue) AS 收入额 FROM fact_revenue r '
        "JOIN dim_unit u ON u.unit_id = r.unit_id WHERE substr(r.month,1,4) = '2026' "
        'GROUP BY u.unit_name ORDER BY 收入额 DESC LIMIT 10", "chart": "bar", "explanation": "按单元汇总2026年收入并降序取前十"}',
    ),
    (
        "2026年各产品线收入占比",
        '{"sql": "SELECT pl.line_name AS 产品线, SUM(r.revenue) AS 收入额, '
        "ROUND(SUM(r.revenue)*100.0/(SELECT SUM(revenue) FROM fact_revenue WHERE substr(month,1,4)='2026'),1) AS 占比 "
        "FROM fact_revenue r JOIN dim_product_line pl ON pl.product_line_id = r.product_line_id "
        "WHERE substr(r.month,1,4) = '2026' GROUP BY pl.line_name ORDER BY 收入额 DESC\", "
        '"chart": "pie", "explanation": "按产品线汇总收入并计算占比"}',
    ),
]


def build_messages(question: str, ddl: str) -> list[dict]:
    examples = "\n\n".join(f"问：{q}\n答：{a}" for q, a in FEW_SHOTS)
    user = (
        f"# 可用表结构\n{ddl}\n\n"
        f"# 示例\n{examples}\n\n"
        f"# 用户问题\n{question}\n\n"
        "请输出 JSON。"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def build_retry_messages(messages: list[dict], error: str) -> list[dict]:
    """SQL 执行失败后，把错误信息回灌给模型再试一次。"""
    return messages + [
        {"role": "assistant", "content": "（上一次生成的 SQL 执行失败）"},
        {"role": "user", "content": f"SQLite 报错：{error}\n请修正 SQL 后重新输出同样的 JSON 结构，不要输出解释。"},
    ]
