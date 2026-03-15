from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse

from app.config import FRONTEND_ORIGIN
from app.routers.chat import router as chat_router
from app.routers.chat_stream import router as chat_stream_router
from app.routers.health import router as health_router
from app.routers.root import router as root_router
from app.routers.upload_img import router as upload_img_router
from app.routers.upload_file import router as upload_file_router
from app.routers.user import router as user_router
from app.routers.sessions import router as sessions_router
from app.config import BACKEND_ORIGIN
import uvicorn


app = FastAPI(title="Health Assistant Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(root_router)
app.include_router(chat_router)
app.include_router(chat_stream_router)
app.include_router(upload_img_router)
app.include_router(upload_file_router)
app.include_router(user_router)
app.include_router(sessions_router)


def parse_port_from_origin(origin: str | None, default_port: int = 6000) -> int:
    """
    从后端 origin（如 http://localhost:6000）中解析出端口号，用于本地直接运行时启动 uvicorn。

    入参说明：
    - origin (str | None)：后端服务的 origin 字符串，通常来自 .env 的 BACKEND_ORIGIN。
    - default_port (int)：当 origin 为空或无法解析端口时使用的默认端口。

    返回值说明：
    - int：解析得到的端口号。

    关键逻辑备注：
    - 优先使用 URL 中显式声明的端口；若缺失或解析失败，则回退到默认端口。
    """
    if not origin:
        return default_port
    try:
        parsed = urlparse(origin)
        return int(parsed.port) if parsed.port else default_port
    except Exception:
        return default_port


if __name__ == "__main__":
    """
    直接运行此模块时使用 config 中的 BACKEND_ORIGIN 启动 uvicorn，
    端口与 .env 中 BACKEND_ORIGIN 保持一致。
    """
    uvicorn.run("app.main:app", host="0.0.0.0", port=parse_port_from_origin(BACKEND_ORIGIN))
