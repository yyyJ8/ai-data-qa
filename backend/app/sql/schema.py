"""Schema 目录与召回。

目录（catalog）是给模型看的语义层：表、字段的中文含义、粒度、口径。
它必须与真实库一致——测试里用 PRAGMA 校验，防止改表后忘记改目录。

召回策略：维度表永远带上（体积小、连接必需），事实表按问题关键词打分取前 k。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Table:
    name: str
    desc: str
    grain: str
    columns: dict[str, str]


CATALOG: dict[str, Table] = {
    "dim_unit": Table(
        "dim_unit", "经营单元维度", "一行一个经营单元",
        {"unit_id": "单元ID", "unit_name": "单元名称，如 北京代表处", "unit_type": "类型：办事处/代表处/系统部/渠道部", "region": "大区：华北/华东/华南/华中/西北/西南/东北/总部"},
    ),
    "dim_industry": Table(
        "dim_industry", "行业维度", "一行一个行业",
        {"industry_id": "行业ID", "industry_name": "行业名称，如 数字政府", "industry_category": "行业大类：政企/商业市场/渠道"},
    ),
    "dim_product_line": Table(
        "dim_product_line", "产品线维度", "一行一条产品线",
        {"product_line_id": "产品线ID", "line_name": "产品线：通用计算/智能计算/商业解决方案"},
    ),
    "dim_product": Table(
        "dim_product", "产品型号维度", "一行一个型号",
        {"model_id": "型号ID", "model_name": "型号名称，如 R5300 G5", "product_line_id": "所属产品线"},
    ),
    "dim_customer": Table(
        "dim_customer", "客户维度", "一行一个客户",
        {"customer_id": "客户ID", "customer_name": "客户名称", "industry_id": "所属行业"},
    ),
    "fact_target": Table(
        "fact_target", "年度目标", "一行 = 年 × 单元 × 产品线",
        {"year": "年份，2025 或 2026", "unit_id": "经营单元", "product_line_id": "产品线", "commercial_target": "商业目标（不含税签约额，万元）", "sol_target": "商解目标（不含税收入，万元），仅商业解决方案行有值"},
    ),
    "fact_revenue": Table(
        "fact_revenue", "月度收入明细", "一行 = 月 × 单元 × 行业 × 产品线 × 型号 × 客户",
        {"month": "月份，格式 YYYY-MM", "unit_id": "经营单元", "industry_id": "行业", "product_line_id": "产品线", "model_id": "产品型号", "customer_id": "客户", "revenue": "不含税收入（万元）", "contract_amount": "不含税签约额（万元）"},
    ),
    "fact_order": Table(
        "fact_order", "订单", "一行一张订单",
        {"order_id": "订单ID", "contract_no": "合同号", "unit_id": "经营单元", "customer_id": "客户", "product_line_id": "产品线", "sign_date": "签约日期 YYYY-MM-DD", "amount": "签约金额（万元）", "status": "状态：已签约/执行中/已验收/已关闭"},
    ),
    "fact_collection": Table(
        "fact_collection", "月度回款", "一行 = 月 × 单元",
        {"month": "月份 YYYY-MM", "unit_id": "经营单元", "plan_amount": "计划回款（万元）", "actual_amount": "实际回款（万元）"},
    ),
    "fact_ppl": Table(
        "fact_ppl", "PPL 项目明细", "一行一个项目",
        {"project_id": "项目ID", "contract_no": "合同号", "unit_id": "经营单元", "industry_id": "行业", "product_line_id": "产品线", "model_id": "型号", "amount": "项目金额（万元）", "stage": "阶段：商机/方案/投标/商务/签约/交付", "risk_delivery": "交付风险：低/中/高", "risk_payment": "回款风险：低/中/高", "risk_overall": "整体风险：低/中/高", "expected_sign_date": "预计签约日期"},
    ),
    "v_unit_overall": Table(
        "v_unit_overall", "视图：单元维度年度完成情况", "一行 = 年 × 单元，已按单元聚合，问「哪个单元完成率最高/最低」用它",
        {"year": "年份", "unit_name": "单元名称", "commercial_target": "商业目标合计", "revenue": "收入合计", "completion_rate": "完成率（百分数，78.5 表示 78.5%）"},
    ),
    "v_line_year": Table(
        "v_line_year", "视图：产品线年度收入", "已按年聚合，可直接查同比",
        {"year": "年份（整数）", "line_name": "产品线", "revenue": "收入", "contract_amount": "签约额"},
    ),
}

DIM_TABLES = ["dim_unit", "dim_industry", "dim_product_line", "dim_product", "dim_customer"]

# 底座表：几乎每个问题都要用到，恒定召回
BASE_TABLES = DIM_TABLES + ["fact_revenue"]

# 业务词 → 事实表（命中即加分）
KEYWORDS: dict[str, list[str]] = {
    "fact_revenue": ["收入", "营收", "销售额", "业绩", "金额", "卖", "销售"],
    "fact_target": ["目标", "完成率", "达成", "指标", "考核"],
    "fact_order": ["订单", "合同", "签约", "合同额", "下单"],
    "fact_collection": ["回款", "收款", "到账", "应收", "账期"],
    "fact_ppl": ["项目", "风险", "PPL", "阶段", "商机", "交付"],
    "v_unit_overall": ["完成率", "达成率", "目标达成", "完成情况"],
    "v_line_year": ["产品线同比", "同比", "增长"],
}


def recall(query: str, k: int = 2) -> list[str]:
    """返回本次问数需要喂给模型的表清单。

    维度表与 fact_revenue 是绝大多数问题的底座，恒定包含；
    事实表/视图再按关键词得分补 k 张，避免把 fact_revenue 挤出去。
    """
    text = query.lower()
    scored: list[tuple[int, str]] = []
    for table, words in KEYWORDS.items():
        score = sum(1 for w in words if w.lower() in text)
        if score:
            scored.append((score, table))
    scored.sort(key=lambda x: (-x[0], x[1]))

    selected = list(BASE_TABLES)
    for _, table in scored[:k]:
        if table not in selected:
            selected.append(table)
    return selected


def render_ddl(tables: list[str]) -> str:
    """把目录渲染成紧凑的 DDL 说明，作为 prompt 的一部分。"""
    blocks: list[str] = []
    for name in tables:
        table = CATALOG.get(name)
        if not table:
            continue
        cols = "\n".join(f"  {col}  -- {desc}" for col, desc in table.columns.items())
        blocks.append(f"-- {table.desc}（{table.grain}）\n{table.name}(\n{cols}\n)")
    return "\n\n".join(blocks)


def catalog_mismatch(conn: sqlite3.Connection) -> list[str]:
    """目录与真实库的不一致项；空列表表示一致。测试用。"""
    problems: list[str] = []
    for name, table in CATALOG.items():
        rows = conn.execute(f"PRAGMA table_info({name})").fetchall()
        if not rows:
            problems.append(f"{name} 在库中不存在")
            continue
        actual = [r[1] for r in rows]
        expected = list(table.columns)
        if actual != expected:
            problems.append(f"{name} 字段不一致: 库={actual} 目录={expected}")
    return problems
