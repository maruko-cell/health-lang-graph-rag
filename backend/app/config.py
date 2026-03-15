import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

# 明确指定项目根目录下的 .env 路径，避免工作目录变化导致读取失败
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
BACKEND_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(dotenv_path=ENV_PATH)


def _load_neo4j_yaml() -> Optional[Dict[str, Any]]:
    """
    从单独 YAML 文件加载 Neo4j 配置；支持 NEO4J_CONFIG_PATH 指定路径。

    入参：无入参，路径由环境变量或默认 backend/neo4j.yaml 决定。

    返回值：database.neo4j 的字典，或 None（文件不存在/解析失败时）。
    """
    path_env = os.getenv("NEO4J_CONFIG_PATH")
    path = Path(path_env) if path_env else (BACKEND_ROOT / "neo4j.yaml")
    if not path.is_file():
        return None
    try:
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or not isinstance(data, dict):
            return None
        db = data.get("database")
        if not db or not isinstance(db, dict):
            return None
        return db.get("neo4j") if isinstance(db.get("neo4j"), dict) else None
    except Exception:
        return None


_neo4j_cfg = _load_neo4j_yaml()


def _neo4j(key: str, env_key: str, default: Optional[str] = None) -> Optional[str]:
    """优先取环境变量，否则取 YAML 中 key 对应值。"""
    v = os.getenv(env_key)
    if v is not None and v != "":
        return v
    if _neo4j_cfg and key in _neo4j_cfg and _neo4j_cfg[key] is not None:
        return str(_neo4j_cfg[key])
    return default


def _yaml_value_to_str_list(v: Any) -> List[str]:
    """
    将 YAML 值转为非空字符串列表（供 node-label、relationship-type 及意图模板列表字段复用）。
    入参：v 任意值（None、列表或标量）。返回：去空、去空串的字符串列表。
    """
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if x is not None and str(x).strip()]
    return [str(v).strip()] if str(v).strip() else []


def _neo4j_list(yaml_key: str) -> List[str]:
    """从 YAML 中读取列表配置（如 node-label、relationship-type）。"""
    if not _neo4j_cfg or yaml_key not in _neo4j_cfg:
        return []
    return _yaml_value_to_str_list(_neo4j_cfg[yaml_key])


def _normalize_intent_template(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 YAML 意图模板的键转为 snake_case，并规范列表/布尔值。
    入参：raw 单条意图模板原始字典。返回：规范化后的模板字典。
    """
    key_map = {
        "start-label": "start_label",
        "relationship-type": "relationship_type",
        "end-label": "end_label",
        "entity-type": "entity_type",
        "param-key": "param_key",
        "dynamic-rels": "dynamic_rels",
        "end-multi-label": "end_multi_label",
    }

    out: Dict[str, Any] = {}
    for k, v in raw.items():
        new_key = key_map.get(k, k)
        if new_key in ("start_label", "relationship_type", "end_label"):
            out[new_key] = _yaml_value_to_str_list(v)
        elif new_key in ("dynamic_rels", "end_multi_label"):
            out[new_key] = bool(v) if v is not None else False
        elif new_key in ("entity_type", "param_key"):
            out[new_key] = str(v).strip() if v is not None else ""
        else:
            out[new_key] = v
    return out


def get_intent_templates() -> Dict[str, Dict[str, Any]]:
    """
    从 neo4j.yaml 的 intent-templates 读取意图模板，键转为 snake_case。
    入参：无。返回：意图名 -> 模板字典（含 start_label、relationship_type、end_label、entity_type、param_key、dynamic_rels、end_multi_label）。
    """
    if not _neo4j_cfg or "intent-templates" not in _neo4j_cfg:
        return {}
    raw_templates = _neo4j_cfg["intent-templates"]
    if not isinstance(raw_templates, dict):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for intent_name, raw in raw_templates.items():
        if not isinstance(raw, dict):
            continue
        result[str(intent_name).strip()] = _normalize_intent_template(raw)
    return result


# 基础 LLM 配置
DEFAULT_LLM = os.getenv("DEFAULT_LLM")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")

# Neo4j 配置（优先 .env，否则从 backend/config/neo4j.yaml 读取）
NEO4J_URI = _neo4j("url", "NEO4J_URI")
NEO4J_USER = _neo4j("username", "NEO4J_USER")
NEO4J_PASSWORD = _neo4j("password", "NEO4J_PASSWORD")
NEO4J_DATABASE = _neo4j("database", "NEO4J_DATABASE")
NEO4J_SEARCH_KEY = _neo4j("search-key", "NEO4J_SEARCH_KEY") or "名称"
NEO4J_NODE_LABELS: List[str] = _neo4j_list("node-label")
NEO4J_RELATIONSHIP_TYPES: List[str] = _neo4j_list("relationship-type")

# 前后端地址
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")
BACKEND_ORIGIN = os.getenv("BACKEND_ORIGIN")

# 敏感词配置
SENSITIVE_WORDS = os.getenv("SENSITIVE_WORDS")
SENSITIVE_REPLACEMENT = os.getenv("SENSITIVE_REPLACEMENT")

# 当前用户占位（未登录时从 .env 读取，后续登录后由 token 解析）
USER_ID = os.getenv("USER_ID", "default_user")
# 用户画像默认值（.env 配置，自画像等使用；后续可改为从用户画像扩展录入）
USER_NAME = (os.getenv("USER_NAME") or "").strip() or None
USER_SEX = (os.getenv("USER_SEX") or "").strip() or None
_user_age = (os.getenv("USER_AGE") or "").strip()
USER_AGE = int(_user_age) if _user_age.isdigit() else None
_user_height = (os.getenv("USER_HEIGHT") or "").strip()
USER_HEIGHT = int(_user_height) if _user_height.isdigit() else None
_user_weight = (os.getenv("USER_WEIGHT") or "").strip()
USER_WEIGHT = float(_user_weight) if _user_weight.replace(".", "", 1).isdigit() else None
USER_BMI = (os.getenv("USER_BMI") or "").strip() or None
USER_BMI_CATEGORY = (os.getenv("USER_BMI_CATEGORY") or "").strip() or None

# Redis / 记忆配置
REDIS_URL = os.getenv("REDIS_URL")
SHORT_TERM_MEMORY_TTL_ENV = os.getenv("SHORT_TERM_MEMORY_TTL")
SHORT_TERM_MEMORY_TTL = int(SHORT_TERM_MEMORY_TTL_ENV) if SHORT_TERM_MEMORY_TTL_ENV is not None else None
SHORT_TERM_MEMORY_MAX_TURNS_ENV = os.getenv("SHORT_TERM_MEMORY_MAX_TURNS")
SHORT_TERM_MEMORY_MAX_TURNS = int(SHORT_TERM_MEMORY_MAX_TURNS_ENV) if SHORT_TERM_MEMORY_MAX_TURNS_ENV is not None else 20
# 长期记忆与用户画像：是否在图结束后执行抽取并写入 Redis
LONG_TERM_MEMORY_ENABLED_ENV = os.getenv("LONG_TERM_MEMORY_ENABLED")
LONG_TERM_MEMORY_ENABLED = LONG_TERM_MEMORY_ENABLED_ENV is None or str(LONG_TERM_MEMORY_ENABLED_ENV).lower() in ("1", "true", "yes")
PROFILE_UPDATE_ENABLED_ENV = os.getenv("PROFILE_UPDATE_ENABLED")
PROFILE_UPDATE_ENABLED = PROFILE_UPDATE_ENABLED_ENV is None or str(PROFILE_UPDATE_ENABLED_ENV).lower() in ("1", "true", "yes")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR")

# Chroma 知识库集合名（与 RAG 检索、上传向量化共用）
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME")

# Embedding 接口（OpenAI 兼容），用于知识库向量化与 RAG 检索
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL")
DASHSCOPE_EMBEDDING_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL")

# 会话/Agent 配置
CHAT_MODE = os.getenv("CHAT_MODE")
AGENT_TYPE = os.getenv("AGENT_TYPE")

# OpenAI 兼容接口
OPENAI_API_KEY1 = os.getenv("OPENAI_API_KEY1")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

# 魔域
MOYU_API_KEY = os.getenv("MOYU_API_KEY")
MOYU_BASE_URL = os.getenv("MOYU_BASE_URL")

# 阿里云百炼
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL")
DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL")

# 智谱
ZHIPUAI_API_KEY = os.getenv("ZHIPUAI_API_KEY")
ZHIPUAI_URL = os.getenv("ZHIPUAI_URL")
ZHIPUAI_IMAGE_DESCRIBE_MODEL = os.getenv("ZHIPUAI_IMAGE_DESCRIBE_MODEL")
ZHIPUAI_MODEL = os.getenv("ZHIPUAI_MODEL")
# 自画像生成模型（智谱图像生成 API）
ZHIPUAI_SELF_MODEL = os.getenv("ZHIPUAI_SELF_MODEL")

# Tavily
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# 高德地图 MCP
AMAP_MCP_URL = os.getenv("AMAP_MCP_URL")
AMAP_MCP_TIMEOUT = os.getenv("AMAP_MCP_TIMEOUT")

# 图片上传配置
IMAGE_ALLOWED_TYPES = os.getenv("IMAGE_ALLOWED_TYPES")

# 知识库文件上传配置（如 PDF、Word、纯文本等）
KB_ALLOWED_TYPES = os.getenv("KB_ALLOWED_TYPES")

# HuggingFace 镜像
HF_ENDPOINT = os.getenv("HF_ENDPOINT")

# 硅基流动
SILICON_API_KEY = os.getenv("SILICON_API_KEY")

# 阿里云 OSS（固定使用 STS AssumeRole 临时凭证访问）；strip 避免 .env 首尾空格导致 InvalidAccessKeyId
OSS_ACCESS_KEY_ID = (os.getenv("OSS_ACCESS_KEY_ID") or "").strip() or None
OSS_ACCESS_KEY_SECRET = (os.getenv("OSS_ACCESS_KEY_SECRET") or "").strip() or None
OSS_REGION = os.getenv("OSS_REGION", "cn-hangzhou")
OSS_BUCKET = os.getenv("OSS_BUCKET")
OSS_OBJECT_PREFIX = os.getenv("OSS_OBJECT_PREFIX", "images/")
OSS_IMAGE_PREFIX = os.getenv("OSS_IMAGE_PREFIX", "images/")
OSS_FILE_PREFIX = os.getenv("OSS_FILE_PREFIX", "files/")
OSS_STS_ROLE_ARN = os.getenv("OSS_STS_ROLE_ARN")
OSS_STS_ROLE_SESSION_NAME = os.getenv("OSS_STS_ROLE_SESSION_NAME", "oss-upload-session")
OSS_STS_ENDPOINT = os.getenv("OSS_STS_ENDPOINT", "sts.aliyuncs.com")
OSS_STS_DURATION_SECONDS_ENV = os.getenv("OSS_STS_DURATION_SECONDS")
OSS_STS_DURATION_SECONDS = int(OSS_STS_DURATION_SECONDS_ENV) if OSS_STS_DURATION_SECONDS_ENV else 3600

# Query 重写：摘要方式参与轮数与长度限制（直接使用 .env 配置）
QUERY_REWRITE_SUMMARY_MAX_TURNS = int(os.getenv("QUERY_REWRITE_SUMMARY_MAX_TURNS", "3"))
QUERY_REWRITE_SUMMARY_MAX_INPUT_LEN = int(os.getenv("QUERY_REWRITE_SUMMARY_MAX_INPUT_LEN", "800"))
QUERY_REWRITE_SUMMARY_MAX_LEN = int(os.getenv("QUERY_REWRITE_SUMMARY_MAX_LEN", "80"))

