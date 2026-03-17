# health-lang-graph-rag

A health assistant built on **LangGraph** and **RAG**. It uses a decoupled frontend/backend architecture. The backend orchestrates multiple capability subgraphs (RAG, diet, exercise, multimodal, nearby map, user profile, etc.), then merges everything in a Summary node and streams the final response.

---

## Features

- **Intent routing**: after query rewriting, requests are routed by intent to RAG / diet / exercise / multimodal / nearby map / user profile / fallback subgraphs
- **RAG retrieval**: Neo4j knowledge graph + Chroma vectors + keyword search, fused with RRF
- **Memory & profile**: Redis short/long-term memory and user profile updates
- **Streaming chat**: the `chat_stream` endpoint supports SSE streaming
- **Extensibility**: AMap MCP, Alibaba Cloud OSS, knowledge-base upload and vectorization tasks

---

## Tech stack

| Layer | Tech |
|--------|------|
| Frontend | React 19 + TypeScript + Vite 7 + Ant Design / Ant Design Mobile + Sass |
| Backend | FastAPI + LangGraph + Python 3.13+ |
| Retrieval | Neo4j (knowledge graph), Chroma (vectors), keyword search, RRF fusion |
| Memory | Redis (short/long-term memory, user profile) |
| Optional | AMap MCP, Alibaba Cloud OSS, multi-LLM (OpenAI-compatible / DashScope / Zhipu / Ollama, etc.) |

---

## Project structure

```
health-lang-graph-rag/
├── frontend/                 # Frontend: Vite + React
│   ├── src/
│   └── package.json
├── backend/                  # Backend: FastAPI + LangGraph
│   ├── app/
│   │   ├── main.py           # FastAPI entrypoint
│   │   ├── state.py          # Graph state definition
│   │   ├── config.py         # Config (loads .env)
│   │   ├── llm_agent/        # Unified LLM wrappers
│   │   ├── nodes/            # Graph nodes and subgraphs
│   │   │   ├── super.py      # Super graph: query_rewrite → route → subgraph → summary
│   │   │   ├── intent.py     # Intent detection and routing
│   │   │   ├── query_rewrite.py
│   │   │   ├── rag.py        # RAG subgraph (KG + vectors + fusion)
│   │   │   ├── diet.py       # Diet
│   │   │   ├── exercise.py   # Exercise (device data + metrics + report)
│   │   │   ├── multi_moda.py # Multimodal
│   │   │   ├── surround_amap_maps_mcp.py  # Nearby AMap
│   │   │   ├── selfie.py     # User profile ("selfie")
│   │   │   ├── default_handler.py  # Fallback
│   │   │   ├── summary.py    # Final response summarization
│   │   │   └── retrievers/   # Retrieval implementations (neo4j, vector, keyword, rrf, rag)
│   │   ├── routers/          # API routes (chat, chat_stream, sessions, health, upload, etc.)
│   │   ├── api/              # Knowledge-base upload, OSS, etc.
│   │   ├── tasks/            # Vectorization and other tasks
│   │   ├── memory/           # Redis memory and user profile
│   │   └── common/           # Shared utilities (prompts, embeddings, MCP, etc.)
│   └── pyproject.toml        # Dependencies and Python version
├── task_graph.puml           # Super graph PlantUML diagram (see below)
├── .env.example              # Backend env template (copy to project root as .env)
├── package.json              # Root scripts: dev / dev:backend / dev:frontend
└── README.md
```

---

## Requirements

- **Knowledge graph dataset**: you can start from sources like [OpenKG Medical Knowledge Graph](http://data.openkg.cn/ne/dataset/medicalgraph)
- **Node.js**: for frontend build and development
- **Python ≥ 3.13**: backend runtime; `uv` is recommended
- **Neo4j**: knowledge graph DB, default `bolt://localhost:7687`; default config file is **`backend/neo4j.yaml`** (consistent with `app/config.py`, can be overridden via `NEO4J_CONFIG_PATH`)
- **Redis**: memory and user profile, default `redis://localhost:6379/0`
- Optional: Chroma, AMap MCP, OSS, LLM API keys

---

## Setup & run

> To run locally after cloning, **finish environment configuration first: copy `.env.example` to `.env` and fill in required values** (see Backend/Frontend sections below). Otherwise the app may fail to start or be unable to connect to Neo4j/Redis/LLM services.

### 1. Backend

```bash
# Required: copy the env template to .env in the project root (backend reads .env from project root)
cp .env.example .env
# Examples of required values: DEFAULT_LLM, NEO4J_*, REDIS_URL, FRONTEND_ORIGIN, BACKEND_ORIGIN, and at least one LLM config (e.g. DASHSCOPE_* / OPENAI_*)

cd backend
# Create a virtual environment and install dependencies with uv (recommended)
uv venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync
```

### 2. Frontend

```bash
cd frontend
npm install
# Required: copy the env template to .env and fill it in (otherwise requests to backend may fail)
cp .env.example .env
# Edit .env: set VITE_BACKEND_ORIGIN to your backend origin (e.g. http://localhost:4000)
```

### 3. Run

**Option A: start frontend + backend from project root**

```bash
npm run dev
```

> Windows PowerShell does not support `&&`. If scripts use `&` to run in parallel, it will work; otherwise use Option B to start them separately.

**Option B: start separately (recommended for Windows or debugging)**

```bash
# Terminal 1: backend (default port is in .env via BACKEND_ORIGIN, e.g. 4000)
npm run dev:backend

# Terminal 2: frontend (default http://localhost:5173)
npm run dev:frontend
```

**Backend only (from `backend` directory):**

```bash
cd backend
.venv/bin/python -m app.main
# Windows: .venv\Scripts\python -m app.main
```

---

## `task_graph.puml` overview

The project root **`task_graph.puml`** uses [PlantUML](https://plantuml.com/) to describe the health assistant's LangGraph **super-graph runtime structure**, making the flow easier to review.

**Flow summary:**

1. **start** → **query_rewrite** (query rewrite)
2. → **router _router_super**: branch by intent
3. → one of the following subgraphs:
   - `rag` → rag_subgraph
   - `multi_moda` → multi_moda_subgraph
   - `diet` → diet_subgraph
   - `exercise` → exercise_subgraph
   - `amap` → surround_amap_maps_mcp_subgraph
   - `selfie` → selfie_subgraph
   - others → default_handler_subgraph
4. → **summary_subgraph** (final_reply summary) → **stop**

**How to view:** open `task_graph.puml` with a PlantUML plugin or an online service (e.g. [PlantUML Server](http://www.plantuml.com/plantuml/uml/)) to render the diagram.

---

## Architecture at a glance

- **Super graph**: `query_rewrite` → router node → choose subgraph by intent (rag / diet / exercise / multi_moda / surround_amap_maps_mcp / selfie / default) → **summary** → END. See **`task_graph.puml`**.
- **RAG subgraph**: entity extraction → Neo4j Cypher / vector / keyword retrieval → RRF fusion → answer generation.
- **Exercise subgraph**: load device data → compute metrics → generate report.
- Chat supports streaming output (`chat_stream`); memory and user profile are maintained by Redis and the `memory` module.

---

## Contributing

1. Fork this repository  
2. Create a new branch (e.g. `Feat_xxx`)  
3. Commit your changes and push the branch  
4. Open a Pull Request  
