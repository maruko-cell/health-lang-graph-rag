from fastapi import APIRouter


router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    """
    根路径测试接口。

    入参：
    无入参。

    返回值：
    dict[str, str]：返回后端服务运行状态提示信息。

    关键逻辑：
    用于快速验证后端服务是否正常启动并可对外提供服务。
    """
    return {"message": "Health Assistant Backend is running"}

