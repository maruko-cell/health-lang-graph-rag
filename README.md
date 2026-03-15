# health-lang-graph-rag

基于 **LangGraph** 与 **RAG** 的健康助手：前后端分离，后端以图编排多能力子图（RAG、饮食、运动、多模态、周边地图、自画像等），统一经 Summary 汇总后流式返回。

---

## 功能特性

- **意图路由**：查询重写后按意图分发到 RAG、饮食、运动、多模态、周边地图、自画像或兜底子图
- **RAG 检索**：Neo4j 知识图谱 + Chroma 向量 + 关键词检索，RRF 融合
- **记忆与画像**：Redis 短期/长期记忆、用户画像更新
- **流式对话**：`chat_stream` 接口支持 SSE 流式输出
- **扩展能力**：高德地图 MCP、阿里云 OSS、知识库上传与向量化任务

---

## 技术栈

| 层级   | 技术 |
|--------|------|
| 前端   | React 19 + TypeScript + Vite 7 + Ant Design / Ant Design Mobile + Sass |
| 后端   | FastAPI + LangGraph + Python 3.13+ |
| 检索   | Neo4j（知识图谱）、Chroma（向量）、关键词检索，RRF 融合 |
| 记忆   | Redis（短期/长期记忆、用户画像） |
| 可选   | 高德地图 MCP、阿里云 OSS、多 LLM（OpenAI 兼容 / 百炼 / 智谱 / Ollama 等） |

---

## 项目结构

```
health-lang-graph-rag/
├── frontend/                 # 前端：Vite + React
│   ├── src/
│   └── package.json
├── backend/                  # 后端：FastAPI + LangGraph
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── state.py          # 图状态定义
│   │   ├── config.py         # 配置（含 .env 读取）
│   │   ├── llm_agent/        # LLM 统一封装
│   │   ├── nodes/            # 图节点与子图
│   │   │   ├── super.py      # 总图编排：query_rewrite → 路由 → 子图 → summary
│   │   │   ├── intent.py     # 意图识别与路由
│   │   │   ├── query_rewrite.py
│   │   │   ├── rag.py        # RAG 子图（KG + 向量 + 融合）
│   │   │   ├── diet.py       # 饮食
│   │   │   ├── exercise.py   # 运动（设备数据 + 指标 + 报告）
│   │   │   ├── multi_moda.py # 多模态
│   │   │   ├── surround_amap_maps_mcp.py  # 周边高德地图
│   │   │   ├── selfie.py     # 自画像
│   │   │   ├── default_handler.py  # 兜底
│   │   │   ├── summary.py    # 汇总回复
│   │   │   └── retrievers/   # 检索实现（neo4j、vector、keyword、rrf、rag）
│   │   ├── routers/          # API 路由（chat、chat_stream、sessions、health、upload 等）
│   │   ├── api/              # 知识库上传、OSS 等接口
│   │   ├── tasks/            # 向量化、任务等
│   │   ├── memory/           # Redis 记忆与画像
│   │   └── common/           # 公共工具（Prompt、embedding、MCP 等）
│   └── pyproject.toml        # 依赖与 Python 版本
├── task_graph.puml           # 总图 PlantUML 流程图（见下方说明）
├── .env.example              # 后端环境变量模板（复制到项目根目录 .env 使用）
├── package.json              # 根脚本：dev / dev:backend / dev:frontend
└── README.md
```

---

## 环境要求

- **知识图谱**：可参考 [OpenKG 医学知识图谱](http://data.openkg.cn/ne/dataset/medicalgraph) 等数据源
- **Node.js**：前端构建与开发
- **Python ≥ 3.13**：后端，推荐使用 `uv` 管理
- **Neo4j**：知识图谱，默认 `bolt://localhost:7687`；配置文件默认为 **`backend/neo4j.yaml`**（与 `app/config.py` 一致，可通过环境变量 `NEO4J_CONFIG_PATH` 覆盖）
- **Redis**：记忆与画像，默认 `redis://localhost:6379/0`
- 可选：Chroma、高德 MCP、OSS、各 LLM API Key

---

## 配置与启动

> **克隆后若要本地运行，请先完成环境配置：将 `.env.example` 复制为 `.env`，并按要求填写必填项**（见下方后端/前端小节），否则可能无法启动或无法连接 Neo4j/Redis/LLM 等服务。

### 1. 后端环境

```bash
# 【必做】在项目根目录复制环境变量模板为 .env 并填写必填项（后端从根目录读取 .env）
cp .env.example .env
# 必填示例：DEFAULT_LLM、NEO4J_*、REDIS_URL、FRONTEND_ORIGIN、BACKEND_ORIGIN、至少一套 LLM（如 DASHSCOPE_* / OPENAI_*）

cd backend
# 使用 uv 创建虚拟环境并安装依赖（推荐）
uv venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync
```

### 2. 前端环境

```bash
cd frontend
npm install
# 【必做】复制环境变量模板为 .env 并填写（否则无法正确请求后端）
cp .env.example .env
# 编辑 .env：VITE_BACKEND_ORIGIN 指向后端地址（如 http://localhost:4000）
```

### 3. 启动

**方式一：根目录一键前后端同时启动**

```bash
npm run dev
```

> Windows PowerShell 不支持 `&&`，若脚本使用 `&` 并联启动，可正常使用；否则请用方式二分别启动。

**方式二：分别启动（推荐用于 Windows 或调试）**

```bash
# 终端 1：后端（默认端口见 .env 中 BACKEND_ORIGIN，如 4000）
npm run dev:backend

# 终端 2：前端（默认 http://localhost:5173）
npm run dev:frontend
```

**仅运行后端（在 `backend` 目录下）：**

```bash
cd backend
.venv/bin/python -m app.main
# Windows: .venv\Scripts\python -m app.main
```

---

## task_graph.puml 文件说明

项目根目录下的 **`task_graph.puml`** 使用 [PlantUML](https://plantuml.com/) 描述健康助手 LangGraph **总图运行结构**，便于阅读与评审流程。

**图内流程概览：**

1. **start** → **query_rewrite**（查询重写）
2. → **路由 _router_super**：按意图分支
3. → 下列子图之一：
   - `rag` → rag_subgraph
   - `multi_moda` → multi_moda_subgraph
   - `diet` → diet_subgraph
   - `exercise` → exercise_subgraph
   - `amap` → surround_amap_maps_mcp_subgraph
   - `selfie` → selfie_subgraph
   - 其他 → default_handler_subgraph
4. → **summary_subgraph**（汇总 final_reply）→ **stop**

**使用方式：** 用 PlantUML 插件或在线服务（如 [PlantUML Server](http://www.plantuml.com/plantuml/uml/)）打开 `task_graph.puml` 即可生成流程图。

---

## 架构简述

- **总图（Super）**：`query_rewrite` → 路由节点 → 按意图选子图（rag / diet / exercise / multi_moda / surround_amap_maps_mcp / selfie / default）→ **summary** → END。流程图见 **`task_graph.puml`**。
- **RAG 子图**：实体抽取 → Neo4j Cypher / 向量 / 关键词检索 → RRF 融合 → 生成回答。
- **运动子图**：加载设备数据 → 计算指标 → 生成报告。
- 对话支持流式输出（`chat_stream`），记忆与用户画像由 Redis 与 `memory` 模块维护。

---

## 参与贡献

1. Fork 本仓库  
2. 新建分支（如 `Feat_xxx`）  
3. 提交代码并推送到分支  
4. 提交 Pull Request  
