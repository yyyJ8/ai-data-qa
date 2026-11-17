# AI问数 - 企业级销售经管数据管理平台

> 华鲲振宇 2027 校园招聘 · 实操作业
> 基于 React + FastAPI + LLM 的 text2sql 数据问答平台，实现原型中「数据发现 → 数据表格 → 数据统计 → 数据可视化」四段式问答链路。

## 一、快速开始

```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env   # 填入 LLM API Key

# 2. 一键启动
docker compose up -d

# 3. 访问
# 前端 http://localhost:8000
# 接口文档 http://localhost:8000/docs
```

（本地开发方式见下文「开发说明」）

## 二、技术栈

| 层 | 选型 |
|---|---|
| 前端 | React + TypeScript + Vite，图表用 ECharts |
| 后端 | Python 3.11 + FastAPI |
| 数据 | SQLite（text2sql 目标库），自建销售经管数据集 |
| 模型 | 待定（DeepSeek / 通义） |
| 部署 | Docker Compose，Linux |

## 三、功能清单

> 待补充：对照原型逐项勾选实现状态

- [ ] AI 问数：自然语言提问 → 数据发现 / 表格 / 统计 / 可视化
- [ ] 追问与延伸问题
- [ ] 模型配置
- [ ] 应用配置（开场白、语音开关）
- [ ] 数据管理（台账表格、筛选、导出 Excel）
- [ ] 系统管理（权限、回复校对、常问设置）

## 四、目录结构

```
ai-data-qa/
├── Data/            # 官方原型，只读，未做任何改动（sha256 见 docs/原型诊断.md）
├── backend/         # FastAPI 服务 + text2sql 链路
├── frontend/        # React 前端
├── docs/            # 原型诊断与设计说明
├── samples/         # 示例问句与预期结果
├── docker-compose.yml
└── README.md
```

## 五、原型问题诊断

见 [docs/原型诊断.md](docs/原型诊断.md)。

## 六、AI 使用声明

本项目在开发过程中使用 AI 辅助编码，具体分工与范围见 docs 目录说明。

## 七、开发说明

> 待补充：本地运行前后端的具体命令
