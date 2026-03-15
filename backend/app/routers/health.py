from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    健康检查接口。

    入参：
    无入参。

    返回值：
    dict[str, str]：返回当前服务健康状态的字典。

    关键逻辑：
    始终返回固定的健康状态，用于探活与监控检查。
    """
    return {"status": "ok"}

