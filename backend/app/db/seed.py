"""业务库种子数据生成器。

设计约束：
1. 可复现 —— 固定随机种子，同一份代码任何时候生成同样的数字。
2. 可勾稽 —— 月度收入按年目标拆分，订单金额按月合同额拆分，合计严格相等。
3. 口径一致 —— 商业目标为不含税签约额，收入为不含税收入，完成率 = 收入 / 商业目标。

金额单位统一为「万元」，按整数存储。
"""

from __future__ import annotations

import random
import sqlite3

SEED = 20260101

# --------------------------------------------------------------------------
# 维度数据
# --------------------------------------------------------------------------

# (名称, 类型, 区域, 2026 年商业目标基数/万元)
UNITS: list[tuple[str, str, str, int]] = [
    ("北京代表处", "代表处", "华北", 7950),
    ("上海代表处", "代表处", "华东", 7070),
    ("浙江代表处", "代表处", "华东", 6460),
    ("江苏代表处", "代表处", "华东", 5560),
    ("深圳代表处", "代表处", "华南", 4820),
    ("山东代表处", "代表处", "华东", 4090),
    ("广州代表处", "代表处", "华南", 4200),
    ("川藏代表处", "代表处", "西南", 3100),
    ("湖北办事处", "办事处", "华中", 2900),
    ("福建代表处", "代表处", "华东", 2600),
    ("安徽办事处", "办事处", "华东", 2300),
    ("陕西办事处", "办事处", "西北", 2100),
    ("江西办事处", "办事处", "华东", 2000),
    ("山西办事处", "办事处", "华北", 1900),
    ("辽宁办事处", "办事处", "东北", 1700),
    ("云南代表处", "代表处", "西南", 1600),
    ("新疆代表处", "代表处", "西北", 1200),
    ("内蒙古办事处", "办事处", "华北", 1100),
    ("泛政府系统部", "系统部", "总部", 3600),
    ("金融系统部", "系统部", "总部", 3400),
    ("渠道部", "渠道部", "总部", 5200),
]

# (行业名称, 行业大类)
INDUSTRIES: list[tuple[str, str]] = [
    ("大企业", "政企"),
    ("安平", "政企"),
    ("金融", "政企"),
    ("数字政府", "政企"),
    ("互联网", "商业市场"),
    ("智能制造", "政企"),
    ("交通", "政企"),
    ("医疗", "政企"),
    ("通装", "政企"),
    ("教育", "政企"),
    ("油气矿山", "政企"),
    ("电力", "政企"),
    ("分销/ISV", "渠道"),
    ("JDJG", "商业市场"),
]

PRODUCT_LINES: list[str] = ["通用计算", "智能计算", "商业解决方案"]

PRODUCTS: dict[str, list[str]] = {
    "通用计算": ["R5300 G5", "R5500 G5", "R2900 G5"],
    "智能计算": ["R5900 G5", "R5200 G4", "卡多多"],
    "商业解决方案": ["920", "商解一体机", "行业方案"],
}

# 每个行业的客户名池（合计 112 家）
CUSTOMER_POOL: dict[str, list[str]] = {
    "金融": ["中国银行", "工商银行", "建设银行", "农业银行", "招商银行", "平安银行", "兴业银行", "浦发银行"],
    "数字政府": ["北京市政务云", "浙江省政务云", "广东省政务云", "四川省政务云", "江苏省政务云", "山东省政务云", "湖北省政务云", "陕西省政务云"],
    "互联网": ["阿里巴巴", "腾讯科技", "字节跳动", "美团", "京东", "拼多多", "网易", "百度"],
    "智能制造": ["三一重工", "格力电器", "美的集团", "海尔智家", "比亚迪", "宁德时代", "潍柴动力", "徐工集团"],
    "交通": ["中国铁路", "中国国航", "顺丰速运", "中远海运", "中国邮政", "首都机场", "招商港口", "京东物流"],
    "医疗": ["协和医院", "华西医院", "中山医院", "瑞金医院", "同仁医院", "湘雅医院", "齐鲁医院", "浙大一院"],
    "教育": ["清华大学", "北京大学", "浙江大学", "复旦大学", "上海交大", "南京大学", "武汉大学", "中山大学"],
    "油气矿山": ["中石油", "中石化", "中海油", "国家能源集团", "中煤集团", "紫金矿业", "山东能源", "陕煤集团"],
    "电力": ["国家电网", "南方电网", "华能集团", "大唐集团", "华电集团", "国家电投", "三峡集团", "中广核"],
    "通装": ["中国电子", "中国电科", "航天科技", "航天科工", "兵器工业", "中船重工", "中国信科", "中电太极"],
    "安平": ["公安部一所", "公安部三所", "海康威视", "大华股份", "宇视科技", "科达科技", "东方网力", "高新兴"],
    "大企业": ["中粮集团", "华润集团", "招商局", "中国建筑", "中国中车", "中国商飞", "中国五矿", "中化集团"],
    "分销/ISV": ["神州数码", "联强国际", "伟仕佳杰", "长虹佳华", "翰林汇", "中建材信息", "南天信息", "东华软件"],
    "JDJG": ["军队采购中心", "武警后勤部", "国防科大", "军工保密单位", "装备研究院", "联勤保障部队", "战略支援部队", "军委装备发展部"],
}

# 月度季节权重（1–12 月），2026 年只有 1–9 月
SEASON = [0.90, 0.80, 1.05, 1.00, 1.10, 1.15, 0.95, 0.90, 1.10, 1.05, 1.20, 1.35]

STAGES = ["商机", "方案", "投标", "商务", "签约", "交付"]
STAGE_WEIGHTS = [0.20, 0.20, 0.18, 0.15, 0.15, 0.12]
RISK_LEVELS = ["低", "中", "高"]


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

def split_int(total: int, weights: list[float]) -> list[int]:
    """按权重把整数 total 拆成若干整数，且和严格等于 total（最大余数法）。"""
    if total <= 0:
        return [0 for _ in weights]
    s = sum(weights)
    if s <= 0:
        weights = [1.0 for _ in weights]
        s = float(len(weights))
    raw = [total * w / s for w in weights]
    floors = [int(x) for x in raw]
    remainder = total - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    return floors


def month_str(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def months_of(year: int, cutoff_month: int) -> list[int]:
    return list(range(1, cutoff_month + 1))


# --------------------------------------------------------------------------
# 各表写入
# --------------------------------------------------------------------------

def seed_dimensions(conn: sqlite3.Connection) -> dict[str, int]:
    conn.executemany(
        "INSERT INTO dim_unit(unit_id, unit_name, unit_type, region) VALUES (?,?,?,?)",
        [(i + 1, name, utype, region) for i, (name, utype, region, _) in enumerate(UNITS)],
    )
    conn.executemany(
        "INSERT INTO dim_industry(industry_id, industry_name, industry_category) VALUES (?,?,?)",
        [(i + 1, name, cat) for i, (name, cat) in enumerate(INDUSTRIES)],
    )
    conn.executemany(
        "INSERT INTO dim_product_line(product_line_id, line_name) VALUES (?,?)",
        [(i + 1, name) for i, name in enumerate(PRODUCT_LINES)],
    )

    product_rows = []
    model_id = 1
    for line in PRODUCT_LINES:
        line_id = PRODUCT_LINES.index(line) + 1
        for model in PRODUCTS[line]:
            product_rows.append((model_id, model, line_id))
            model_id += 1
    conn.executemany(
        "INSERT INTO dim_product(model_id, model_name, product_line_id) VALUES (?,?,?)",
        product_rows,
    )

    customer_rows = []
    customer_id = 1
    for industry_name, names in CUSTOMER_POOL.items():
        industry_id = [n for n, _ in INDUSTRIES].index(industry_name) + 1
        for name in names:
            customer_rows.append((customer_id, name, industry_id))
            customer_id += 1
    conn.executemany(
        "INSERT INTO dim_customer(customer_id, customer_name, industry_id) VALUES (?,?,?)",
        customer_rows,
    )

    return {
        "dim_unit": len(UNITS),
        "dim_industry": len(INDUSTRIES),
        "dim_product_line": len(PRODUCT_LINES),
        "dim_product": len(product_rows),
        "dim_customer": len(customer_rows),
    }


def seed_targets(conn: sqlite3.Connection, rng: random.Random) -> dict[str, int]:
    """年度目标：单元 × 产品线；2026 为基数，2025 按单元增速回推。"""
    rows: list[tuple[int, int, int, int, int | None]] = []
    for unit_idx, (_, _, _, base_2026) in enumerate(UNITS, start=1):
        growth = rng.uniform(1.06, 1.22)          # 2026 相对 2025 的增速
        base_2025 = round(base_2026 / growth)
        for year, base in ((2025, base_2025), (2026, base_2026)):
            shares = [0.55 * rng.uniform(0.95, 1.05),
                      0.30 * rng.uniform(0.92, 1.08),
                      0.15 * rng.uniform(0.90, 1.10)]
            targets = split_int(base, shares)
            for line_idx, target in enumerate(targets, start=1):
                sol = round(target * 0.60) if line_idx == 3 else None
                rows.append((year, unit_idx, line_idx, target, sol))
    conn.executemany(
        "INSERT INTO fact_target(year, unit_id, product_line_id, commercial_target, sol_target) VALUES (?,?,?,?,?)",
        rows,
    )
    return {"fact_target": len(rows)}


def seed_revenue(conn: sqlite3.Connection, rng: random.Random) -> dict[str, int]:
    """月度收入明细：年目标 × 完成率 → 月度 → 行业分摊。

    同一 (year, unit, product_line) 的月度收入之和严格等于该年的年收入。
    """
    targets = conn.execute(
        "SELECT year, unit_id, product_line_id, commercial_target FROM fact_target"
    ).fetchall()

    industries = conn.execute("SELECT industry_id, industry_name FROM dim_industry").fetchall()
    industry_names = [row[1] for row in industries]
    models_by_line = {
        line_id: [r[0] for r in conn.execute(
            "SELECT model_id FROM dim_product WHERE product_line_id = ? ORDER BY model_id", (line_id,)
        ).fetchall()]
        for line_id in range(1, len(PRODUCT_LINES) + 1)
    }
    customers_by_industry = {
        industry_id: [r[0] for r in conn.execute(
            "SELECT customer_id FROM dim_customer WHERE industry_id = ? ORDER BY customer_id", (industry_id,)
        ).fetchall()]
        for industry_id, _ in industries
    }

    rows: list[tuple[str, int, int, int, int, int, int, int]] = []
    for year, unit_id, line_id, target in targets:
        rate = rng.uniform(0.62, 1.14)            # 年度完成率
        annual = max(round(target * rate), 1)
        months = months_of(year, 9 if year == 2026 else 12)
        weights = [SEASON[m - 1] * rng.uniform(0.9, 1.1) for m in months]
        monthly = split_int(annual, weights)

        for month, amount in zip(months, monthly):
            if amount <= 0:
                continue
            picked = rng.sample(industries, k=3)
            parts = split_int(amount, [rng.uniform(0.7, 1.3) for _ in picked])
            for (industry_id, _), revenue in zip(picked, parts):
                if revenue <= 0:
                    continue
                model_id = rng.choice(models_by_line[line_id])
                customer_id = rng.choice(customers_by_industry[industry_id])
                contract = round(revenue * rng.uniform(1.02, 1.28))
                rows.append((
                    month_str(year, month), unit_id, industry_id, line_id,
                    model_id, customer_id, revenue, contract,
                ))

    conn.executemany(
        "INSERT INTO fact_revenue(month, unit_id, industry_id, product_line_id, model_id, customer_id, revenue, contract_amount) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    return {"fact_revenue": len(rows)}


def seed_orders(conn: sqlite3.Connection, rng: random.Random) -> dict[str, int]:
    """订单：按月汇总的合同额严格等于该月 fact_revenue.contract_amount 合计。"""
    month_contract = conn.execute(
        """
        SELECT month, unit_id, SUM(contract_amount) AS total,
               MIN(product_line_id) AS line_id
        FROM fact_revenue
        GROUP BY month, unit_id
        ORDER BY month, unit_id
        """
    ).fetchall()

    customers_in_month: dict[tuple[str, int], list[int]] = {}
    for month, unit_id, customer_id in conn.execute(
        "SELECT DISTINCT month, unit_id, customer_id FROM fact_revenue ORDER BY month, unit_id, customer_id"
    ).fetchall():
        customers_in_month.setdefault((month, unit_id), []).append(customer_id)

    rows: list[tuple[int, str, int, int, int, str, int, str]] = []
    seq = 1
    for month, unit_id, total, line_id in month_contract:
        if total <= 0:
            continue
        year, mon = int(month[:4]), int(month[5:7])
        count = rng.randint(2, 4)
        amounts = split_int(total, [rng.uniform(0.6, 1.4) for _ in range(count)])
        customers = customers_in_month[(month, unit_id)]
        for amount in amounts:
            if amount <= 0:
                continue
            day = rng.randint(1, 28)
            if year == 2026 and mon >= 7:
                status = rng.choice(["已签约", "执行中"])
            else:
                status = rng.choices(
                    ["已签约", "执行中", "已验收", "已关闭"], weights=[0.2, 0.2, 0.35, 0.25]
                )[0]
            rows.append((
                seq, f"HT{year}{mon:02d}{seq:05d}", unit_id, rng.choice(customers),
                line_id, f"{year}-{mon:02d}-{day:02d}", amount, status,
            ))
            seq += 1

    conn.executemany(
        "INSERT INTO fact_order(order_id, contract_no, unit_id, customer_id, product_line_id, sign_date, amount, status) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    return {"fact_order": len(rows)}


def seed_collections(conn: sqlite3.Connection, rng: random.Random) -> dict[str, int]:
    """月度回款：计划 = 当月收入 × 系数，实际 = 计划 × 回款比例。"""
    revenue = conn.execute(
        "SELECT month, unit_id, SUM(revenue) FROM fact_revenue GROUP BY month, unit_id ORDER BY month, unit_id"
    ).fetchall()

    rows = []
    for month, unit_id, rev in revenue:
        plan = max(round(rev * rng.uniform(0.85, 0.98)), 1)
        actual = max(round(plan * rng.uniform(0.72, 1.02)), 0)
        rows.append((month, unit_id, plan, actual))

    conn.executemany(
        "INSERT INTO fact_collection(month, unit_id, plan_amount, actual_amount) VALUES (?,?,?,?)",
        rows,
    )
    return {"fact_collection": len(rows)}


def seed_ppl(conn: sqlite3.Connection, rng: random.Random) -> dict[str, int]:
    """PPL 项目明细：400 条，覆盖阶段与风险分布。"""
    units = conn.execute("SELECT unit_id FROM dim_unit ORDER BY unit_id").fetchall()
    industries = conn.execute("SELECT industry_id FROM dim_industry ORDER BY industry_id").fetchall()
    models = conn.execute("SELECT model_id, product_line_id FROM dim_product ORDER BY model_id").fetchall()

    rows = []
    for project_id in range(1, 401):
        unit_id = rng.choice(units)[0]
        industry_id = rng.choice(industries)[0]
        model_id, line_id = rng.choice(models)
        amount = rng.randint(80, 1800)
        stage = rng.choices(STAGES, weights=STAGE_WEIGHTS)[0]
        risk_delivery = rng.choices(RISK_LEVELS, weights=[0.6, 0.28, 0.12])[0]
        risk_payment = rng.choices(RISK_LEVELS, weights=[0.55, 0.3, 0.15])[0]
        rank = {"低": 0, "中": 1, "高": 2}
        risk_overall = risk_delivery if rank[risk_delivery] >= rank[risk_payment] else risk_payment
        mon = rng.randint(1, 12)
        rows.append((
            project_id, f"PPL2026{project_id:05d}", unit_id, industry_id, line_id,
            model_id, amount, stage, risk_delivery, risk_payment, risk_overall,
            f"2026-{mon:02d}-{rng.randint(1, 28):02d}",
        ))

    conn.executemany(
        "INSERT INTO fact_ppl(project_id, contract_no, unit_id, industry_id, product_line_id, model_id, "
        "amount, stage, risk_delivery, risk_payment, risk_overall, expected_sign_date) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    return {"fact_ppl": len(rows)}


def seed_all(conn: sqlite3.Connection) -> dict[str, int]:
    """按固定顺序灌入全部种子数据，返回各表行数。"""
    rng = random.Random(SEED)
    counts: dict[str, int] = {}
    counts.update(seed_dimensions(conn))
    counts.update(seed_targets(conn, rng))
    counts.update(seed_revenue(conn, rng))
    counts.update(seed_orders(conn, rng))
    counts.update(seed_collections(conn, rng))
    counts.update(seed_ppl(conn, rng))
    conn.commit()
    return counts
