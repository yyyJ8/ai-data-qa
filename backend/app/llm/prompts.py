"""Prompt 构造。

约定：模型只输出 JSON，解析失败由调用方重试；口径与语法规则写在 system 里，
避免每次请求都重复解释业务背景。
"""

from __future__ import annotations

SYSTEM_PROMPT = """你是企业销售经管数据的 text2sql 助手。根据用户问题与给定的表结构，生成一条 SQLite 查询。

硬性规则：
1. 只输出一个 JSON 对象，不要 Markdown 代码块，不要解释性文字。
   {"sql": "...", "chart": "bar|line|pie|table|none", "explanation": "一句话说明",
    "followups": ["基于当前结果的追问1", "追问2", "追问3"]}
2. 只生成单条只读 SELECT，禁止任何写操作、PRAGMA、ATTACH；不要以分号结尾。
3. 金额单位是万元，不要做单位换算。
4. 时间字段类型：year 是整数（写 year = 2026，不要加引号）；
   month 是文本 'YYYY-MM'，按年过滤用 substr(month,1,4)='2026'；
   sign_date / expected_sign_date 是文本 'YYYY-MM-DD'。
5. 同比需要同时取 2025 与 2026 两年数据；完成率 = 收入 / 商业目标 * 100。
6. 维度值用中文原文匹配，例如 unit_name='北京代表处'、line_name='通用计算'。
7. 输出列请用中文别名，例如 AS 经营单元、AS 收入额；聚合结果按需要的顺序排序。
8. 问题无法用给定表回答时，输出 {"sql": null, "chart": "none", "explanation": "缺少什么数据"}。
9. 不要输出 SELECT *，只选问题要求的列，不要额外派生无关指标（同比、占比类问题除外）。
10. 排名类必须显式 ORDER BY：问"最高/最快/最大/最小"取 1 条并加 LIMIT 1；
    问"前 N / 后 N / 最低 N"加 LIMIT N；占比要给百分比列。
11. followups 给 2–3 条用户可能追问的短问句（不超过 20 字），必须能基于同一批表回答，
    例如"各单元同比如何？""按行业拆分看看"；不要编号、不要与当前问题重复。
12. 若给了「历史对话」，当前问题可能是省略式追问（如"那同比呢""换成浙江"），
    必须结合上下文补全条件后再生成 SQL。"""


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


def build_messages(question: str, ddl: str, history: list[dict] | None = None) -> list[dict]:
    """history 只取最近 4 条（2 轮），控制 token；assistant 内容截断避免撑爆上下文。"""
    examples = "\n\n".join(f"问：{q}\n答：{a}" for q, a in FEW_SHOTS)
    user = (
        f"# 可用表结构\n{ddl}\n\n"
        f"# 示例\n{examples}\n\n"
        f"# 用户问题\n{question}\n\n"
        "请输出 JSON。"
    )
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in (history or [])[-4:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = str(turn.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": content[:400]})
    messages.append({"role": "user", "content": user})
    return messages


def build_retry_messages(messages: list[dict], error: str) -> list[dict]:
    """SQL 执行失败后，把错误信息回灌给模型再试一次。"""
    return messages + [
        {"role": "assistant", "content": "（上一次生成的 SQL 执行失败）"},
        {"role": "user", "content": f"SQLite 报错：{error}\n请修正 SQL 后重新输出同样的 JSON 结构，不要输出解释。"},
    ]
