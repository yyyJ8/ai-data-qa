# AI问数 - 企业级销售经管数据管理平台

> 华鲲振宇 2027 校园招聘 · 实操作业
> 基于 React + FastAPI + LLM 的 text2sql 数据问答平台，实现原型中「数据发现 → 数据表格 → 数据统计 → 数据可视化」四段式问答链路。

## 一、快速开始

> 状态：**脚手架尚未创建**（`backend/`、`frontend/` 目前只有占位文件）。下面是目标形态，代码落地后即按此执行。

```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env   # 填入 LLM API Key

# 2. 一键启动
docker compose up -d

# 3. 访问
# 前端 http://localhost:8000
# 接口文档 http://localhost:8000/docs
```

当前可先预览官方原型（只读，不要修改）：

```bash
# 任选其一：静态服务器托管 Data/ 目录
npx serve Data
# 或 python -m http.server 8000 --directory Data
```

原型预览用于对照交互，**不是本项目的交付物**。

## 二、技术栈

| 层 | 选型 |
|---|---|
| 前端 | React + TypeScript + Vite，图表用 ECharts |
| 后端 | Python 3.11 + FastAPI |
| 数据 | SQLite（text2sql 目标库），自建销售经管数据集 |
| 模型 | 待定（DeepSeek / 通义） |
| 部署 | Docker Compose，Linux |

## 三、功能清单

状态说明：✅ 已完成 ｜ 🚧 进行中 ｜ ⬜ 未开始

### AI 问数

| 功能 | 状态 | 说明 |
|---|---|---|
| 数据源选择 | ⬜ | 原型有弹窗无入口，需重新设计为可问答数据域 |
| 自然语言提问 → 四段式回答 | 🚧 | 后端链路已可用（命令行），四段式由前端渲染 |
| text2sql 链路 | ✅ | 召回 → 生成 → 校验 → 执行；评测数值命中 30/30 |
| 分析过程可解释 | ⬜ | 选表 → 推理 → SQL → 结果 → 结束（需真实数据） |
| 追问与延伸问题 | ⬜ | 基于结果维度生成，可点击直达 |
| 会话管理 | ⬜ | 新建 / 重命名 / 置顶 / 删除 / 历史列表 |
| 消息操作 | ⬜ | 复制 / 编辑重发 / 重新生成 / 收藏 |
| 快捷提问 | ⬜ | 常问（按频次）/ 收藏 |
| 反馈（数据有误） | ✅ | 回答卡片底部一键提交，进入回复校对列表 |

### 系统管理

| 功能 | 状态 | 说明 |
|---|---|---|
| 模型配置 | ✅ | 页面可选模型/思考参数，连通性测试真实调用，密钥只回显掩码 |
| 应用配置 | ✅ | 开场白、快捷问题、延伸问题开关、常问阈值均可改并即时生效 |
| 回复校对 | ✅ | 处理 + 填写修正 SQL 一键写入评测集（可执行校验、查重） |
| 模型选择生效 | ✅ | 库内配置直接作用于问数链路 |

> 按作业要求，**不实现登录与用户管理**；权限相关能力不做。

### 数据管理

| 功能 | 状态 | 说明 |
|---|---|---|
| 台账表格 | 🚧 | 接口已可用（服务端分页/过滤/排序），前端页待做 |
| 筛选、排序、分页 | ✅ | `GET /api/data/{table}` |
| 导入 Excel | ⬜ | 解析、校验、失败明细 |
| 导出 Excel | ✅ | `GET /api/data/{table}/export`，真实 xlsx |

### 工程与交付

| 事项 | 状态 | 说明 |
|---|---|---|
| 原型功能分析 | ✅ | [docs/功能分析.md](docs/功能分析.md) |
| 原型问题诊断 | ✅ | [docs/原型诊断.md](docs/原型诊断.md) |
| 数据字典 / 口径 | ✅ | [docs/数据字典草稿.md](docs/数据字典草稿.md) |
| 后端 API | ✅ | 健康 / 问数 SSE / 会话 / 配置 / 数据 / 反馈 |
| 前端应用 | ✅ | 四个页面：问数、台账、配置、校对 |
| 评测集（问句-标准 SQL-结果） | ✅ | `samples/eval_cases.jsonl` 30 条，`samples/check_cases.py` 全部可执行 |
| 自动化测试 | ✅ | 后端 76 条 + 前端 Playwright 6 条 |
| Linux 部署 | ⬜ | Docker Compose，单端口对外 |

## 四、目录结构

```
ai-data-qa/
├── Data/                    # 官方原型，只读（sha256 见 docs/原型诊断.md）
│   ├── index.html           # 单文件原型（1.6 MB）
│   └── README.md            # 官方作业要求
├── backend/
│   ├── app/
│   │   ├── api/             # 问数 SSE、会话、配置、数据、反馈
│   │   ├── core/            # 配置加载（.env → Settings）
│   │   ├── db/              # 建表、种子数据、初始化、自检、元数据库
│   │   ├── llm/             # 模型客户端与 Prompt
│   │   ├── services/        # 问数主链路、模型配置
│   │   └── sql/             # 只读校验闸门、表目录与召回
│   ├── scripts/             # ask / eval / check_llm
│   ├── tests/               # 70 条测试
│   └── data/                # 本地 SQLite（已忽略，不入库）
├── docs/
│   ├── 功能分析.md
│   ├── 原型诊断.md
│   ├── 数据字典草稿.md
│   └── 实现计划.md
├── samples/                 # 30 条评测语料、检查脚本、M2 基线报告
├── frontend/                # React 前端（待创建）
├── docker-compose.yml       # 待创建
└── README.md
```

## 五、原型问题诊断

诊断结论：**界面的完成度较高，能力的完成度接近于零。** 共 29 项问题（P0 6 项 / P1 11 项 / P2 12 项），其中最关键的三条：

1. 切换到「智能问数」时因引用不存在的 DOM 元素抛异常，历史会话列表永远为空。
2. AI 回答是固定模板，与提问无关；"分析过程"、SQL、耗时、Token 全部硬编码。
3. 全文件 0 次网络请求，模型配置不产生任何实际调用；API Key 明文存在 localStorage。

详见：

- [docs/原型诊断.md](docs/原型诊断.md) —— 分级问题清单、证据行号、复现方式、修复方向
- [docs/功能分析.md](docs/功能分析.md) —— 模块清单、交互链路、数据结构、真实现 vs 外壳判定
- [docs/数据字典草稿.md](docs/数据字典草稿.md) —— 从原型反推的业务口径、枚举与表结构
- [docs/实现计划.md](docs/实现计划.md) —— 里程碑、架构、接口契约、评测方案与风险

## 六、AI 使用声明

本项目在分析与实现过程中使用 AI 辅助（代码阅读、问题复现、文档起草、编码），分工范围、结论的验证方式与已知限制见 [docs/AI使用声明.md](docs/AI使用声明.md)。

## 七、开发说明

### 7.1 当前阶段

原型分析与问题诊断已完成（见 `docs/`），**实现尚未开始**：`backend/`、`frontend/`、`samples/` 目前只有 `.gitkeep` 占位。

### 7.2 提交约定

- **小步提交**：一个参数、一个组件、一处接口各算一次提交，保证任意一次提交可独立回滚。
- **提交信息**：`type(scope): 说明`，`type` 取 `feat` / `fix` / `docs` / `refactor` / `test` / `chore`。
- **不混提交**：格式化、重命名、依赖升级不与功能改动放在同一次提交里。
- **不提交产物**：`*.db`、`.env`、`node_modules`、`dist` 均已在 `.gitignore` 中排除。

### 7.3 本地开发（已可用）

```powershell
cd backend

# 1. 首次：建虚拟环境并装依赖
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 2. 初始化业务库（幂等，可加 --force 重建）
python -m app.db.init_db
python -m app.db.verify

# 3. 启动服务
uvicorn app.main:app --reload --port 8000
# 健康检查 http://127.0.0.1:8000/api/health
# 接口文档 http://127.0.0.1:8000/docs
```

校验与测试：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/check_llm.py --json --max-tokens 800   # 模型连通性
.\.venv\Scripts\python.exe -m pytest -q                                    # 接口测试
cd .. && python samples/check_cases.py                                     # 评测语料可执行性
```

前端（开发态，需先启动后端）：

```powershell
cd frontend
pnpm install
pnpm dev        # http://127.0.0.1:5173 ，/api 代理到 8000
pnpm build      # 产出 dist/
pnpm e2e        # Playwright 端到端（用系统 Chrome，需前后端可启动）
```

### 7.4 环境变量（规划）

| 变量 | 说明 |
|---|---|
| `LLM_PROVIDER` / `LLM_BASE_URL` | 模型供应方与接入地址 |
| `LLM_API_KEY` | 密钥，仅后端读取，不入库不返前端 |
| `LLM_MODEL` | 默认模型名 |
| `DB_PATH` | SQLite 文件路径 |

### 7.5 数据初始化

数据库由脚本幂等创建（建表 + 灌样例数据），**不提交 `*.db`**；容器启动时自动执行，保证任何环境都能从零复现。

### 7.6 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 存活、模型配置、业务库状态 |
| POST | `/api/chat` | 问数，SSE：`session → stage×3 → table → chart → insight → done` |
| GET | `/api/sessions` | 会话列表（置顶优先） |
| GET | `/api/sessions/{id}` | 会话详情（含消息） |
| PATCH / DELETE | `/api/sessions/{id}` | 改名/置顶、删除 |
| GET / PUT | `/api/config/app` | 开场白、快捷问题、延伸问题开关、常问阈值 |
| GET / PUT | `/api/config/model` | 模型/思考参数；密钥只回显掩码 |
| POST | `/api/config/model/test` | 真实调用一次，返回连通性与延迟 |
| GET | `/api/data/{table}` | 台账分页 + 关键词过滤 + 排序 |
| GET | `/api/data/{table}/export` | 导出真实 xlsx |
| GET / POST | `/api/feedback` | 反馈列表、提交 |
| PATCH | `/api/feedback/{id}` | 处理（状态/备注） |

SSE 示例：

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"2026年收入前3的经营单元"}'
```
