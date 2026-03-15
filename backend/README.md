# 健康助手后端

FastAPI + LangGraph 后端，依赖与整体说明见项目根目录 [README.md](../README.md)。

**配置说明：**

- 环境变量：将根目录 `.env.example` 复制为项目根目录的 `.env` 并填写必填项（`app/config.py` 从根目录读取 `.env`）。
- Neo4j 配置：默认从 **`backend/neo4j.yaml`** 读取（与 `app/config.py` 一致）；可通过环境变量 `NEO4J_CONFIG_PATH` 指定其他路径。
