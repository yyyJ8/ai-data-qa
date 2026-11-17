-- ============================================================================
-- AI问数 · 业务库 Schema（SQLite 3）
-- 单位约定：金额一律为「万元」，按整数存储，避免浮点累计误差。
-- 时间约定：month 为 'YYYY-MM'，日期为 'YYYY-MM-DD'。
-- 口径：商业目标 = 不含税签约额；收入 = 不含税收入；完成率 = 收入 / 商业目标。
-- ============================================================================

PRAGMA user_version = 1;

-- ---------------------------------------------------------------------------
-- 维度：经营单元（21 个）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_unit (
    unit_id    INTEGER PRIMARY KEY,
    unit_name  TEXT NOT NULL UNIQUE,          -- 如「北京代表处」
    unit_type  TEXT NOT NULL,                 -- 办事处 / 代表处 / 系统部 / 渠道部
    region     TEXT NOT NULL                  -- 华北 / 华东 / 华南 / 华中 / 西北 / 西南 / 东北 / 总部
);

-- ---------------------------------------------------------------------------
-- 维度：行业（14 个）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_industry (
    industry_id        INTEGER PRIMARY KEY,
    industry_name      TEXT NOT NULL UNIQUE,  -- 如「数字政府」
    industry_category  TEXT NOT NULL          -- 政企 / 商业市场 / 渠道
);

-- ---------------------------------------------------------------------------
-- 维度：产品线（3 条）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_product_line (
    product_line_id INTEGER PRIMARY KEY,
    line_name       TEXT NOT NULL UNIQUE      -- 通用计算 / 智能计算 / 商业解决方案
);

-- ---------------------------------------------------------------------------
-- 维度：产品型号
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_product (
    model_id        INTEGER PRIMARY KEY,
    model_name      TEXT NOT NULL UNIQUE,     -- 如「R5300 G5」
    product_line_id INTEGER NOT NULL REFERENCES dim_product_line(product_line_id)
);

-- ---------------------------------------------------------------------------
-- 维度：客户
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id   INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL UNIQUE,
    industry_id   INTEGER NOT NULL REFERENCES dim_industry(industry_id)
);

-- ---------------------------------------------------------------------------
-- 事实：年度目标（按 单元 × 产品线）
-- sol_target 仅「商业解决方案」行有值，其余为 NULL。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_target (
    year              INTEGER NOT NULL,       -- 2025 / 2026
    unit_id           INTEGER NOT NULL REFERENCES dim_unit(unit_id),
    product_line_id   INTEGER NOT NULL REFERENCES dim_product_line(product_line_id),
    commercial_target INTEGER NOT NULL,       -- 商业目标（不含税签约额，万元）
    sol_target        INTEGER,                -- 商解目标（不含税收入，万元）
    PRIMARY KEY (year, unit_id, product_line_id)
);

-- ---------------------------------------------------------------------------
-- 事实：月度收入明细（粒度：月 × 单元 × 行业 × 产品线 × 型号 × 客户）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_revenue (
    month            TEXT    NOT NULL,        -- 'YYYY-MM'
    unit_id          INTEGER NOT NULL REFERENCES dim_unit(unit_id),
    industry_id      INTEGER NOT NULL REFERENCES dim_industry(industry_id),
    product_line_id  INTEGER NOT NULL REFERENCES dim_product_line(product_line_id),
    model_id         INTEGER NOT NULL REFERENCES dim_product(model_id),
    customer_id      INTEGER NOT NULL REFERENCES dim_customer(customer_id),
    revenue          INTEGER NOT NULL,        -- 不含税收入（万元）
    contract_amount  INTEGER NOT NULL,        -- 不含税签约额（万元）
    PRIMARY KEY (month, unit_id, industry_id, product_line_id, model_id, customer_id)
);

-- ---------------------------------------------------------------------------
-- 事实：订单（按月汇总口径与 fact_revenue.contract_amount 对齐）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_order (
    order_id        INTEGER PRIMARY KEY,
    contract_no     TEXT NOT NULL UNIQUE,     -- 合同号
    unit_id         INTEGER NOT NULL REFERENCES dim_unit(unit_id),
    customer_id     INTEGER NOT NULL REFERENCES dim_customer(customer_id),
    product_line_id INTEGER NOT NULL REFERENCES dim_product_line(product_line_id),
    sign_date       TEXT NOT NULL,            -- 'YYYY-MM-DD'
    amount          INTEGER NOT NULL,         -- 签约金额（万元）
    status          TEXT NOT NULL             -- 已签约 / 执行中 / 已验收 / 已关闭
);

-- ---------------------------------------------------------------------------
-- 事实：月度回款（计划 / 实际）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_collection (
    month         TEXT    NOT NULL,           -- 'YYYY-MM'
    unit_id       INTEGER NOT NULL REFERENCES dim_unit(unit_id),
    plan_amount   INTEGER NOT NULL,           -- 计划回款（万元）
    actual_amount INTEGER NOT NULL,           -- 实际回款（万元）
    PRIMARY KEY (month, unit_id)
);

-- ---------------------------------------------------------------------------
-- 事实：PPL 项目明细（支撑「高风险项目」「项目阶段」类问题）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_ppl (
    project_id         INTEGER PRIMARY KEY,
    contract_no        TEXT NOT NULL,
    unit_id            INTEGER NOT NULL REFERENCES dim_unit(unit_id),
    industry_id        INTEGER NOT NULL REFERENCES dim_industry(industry_id),
    product_line_id    INTEGER NOT NULL REFERENCES dim_product_line(product_line_id),
    model_id           INTEGER NOT NULL REFERENCES dim_product(model_id),
    amount             INTEGER NOT NULL,      -- 项目金额（万元）
    stage              TEXT NOT NULL,         -- 商机 / 方案 / 投标 / 商务 / 签约 / 交付
    risk_delivery      TEXT NOT NULL,         -- 低 / 中 / 高
    risk_payment       TEXT NOT NULL,         -- 低 / 中 / 高
    risk_overall       TEXT NOT NULL,         -- 低 / 中 / 高
    expected_sign_date TEXT                   -- 'YYYY-MM-DD'
);

-- ---------------------------------------------------------------------------
-- 索引
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_revenue_month       ON fact_revenue(month);
CREATE INDEX IF NOT EXISTS idx_revenue_unit        ON fact_revenue(unit_id, month);
CREATE INDEX IF NOT EXISTS idx_revenue_industry    ON fact_revenue(industry_id, month);
CREATE INDEX IF NOT EXISTS idx_revenue_line        ON fact_revenue(product_line_id, month);
CREATE INDEX IF NOT EXISTS idx_revenue_model       ON fact_revenue(model_id);
CREATE INDEX IF NOT EXISTS idx_order_unit_date     ON fact_order(unit_id, sign_date);
CREATE INDEX IF NOT EXISTS idx_order_status        ON fact_order(status);
CREATE INDEX IF NOT EXISTS idx_ppl_risk            ON fact_ppl(risk_overall);
CREATE INDEX IF NOT EXISTS idx_ppl_stage           ON fact_ppl(stage);

-- ---------------------------------------------------------------------------
-- 视图：单元 × 年度 × 产品线的目标完成情况（供问数与自查复用）
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_unit_year AS
SELECT
    t.year,
    u.unit_name,
    pl.line_name,
    t.commercial_target,
    COALESCE(SUM(r.revenue), 0) AS revenue,
    ROUND(COALESCE(SUM(r.revenue), 0) * 100.0 / NULLIF(t.commercial_target, 0), 1) AS completion_rate
FROM fact_target t
JOIN dim_unit u          ON u.unit_id = t.unit_id
JOIN dim_product_line pl ON pl.product_line_id = t.product_line_id
LEFT JOIN fact_revenue r
       ON r.unit_id = t.unit_id
      AND r.product_line_id = t.product_line_id
      AND substr(r.month, 1, 4) = CAST(t.year AS TEXT)
GROUP BY t.year, u.unit_name, pl.line_name, t.commercial_target;

-- ---------------------------------------------------------------------------
-- 视图：产品线年度收入与同比
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_line_year AS
SELECT
    substr(r.month, 1, 4)    AS year,
    pl.line_name,
    SUM(r.revenue)           AS revenue,
    SUM(r.contract_amount)   AS contract_amount
FROM fact_revenue r
JOIN dim_product_line pl ON pl.product_line_id = r.product_line_id
GROUP BY substr(r.month, 1, 4), pl.line_name;
