"""
将可调用对象加入 FastAPI 后台任务队列，在响应返回后执行，不阻塞上传接口。

入参：
- background_tasks：FastAPI.BackgroundTasks，由路由注入；
- func：可调用对象，例如 vectorize_and_store；
- *args, **kwargs：传给 func 的位置参数与关键字参数。

返回值：无返回值。

关键逻辑：直接调用 background_tasks.add_task(func, *args, **kwargs)，由 FastAPI 在响应发送后执行。
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import BackgroundTasks


def add_task(
    background_tasks: BackgroundTasks,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    将后台任务加入 FastAPI 的 BackgroundTasks，在响应返回后异步执行。

    入参：
    - background_tasks：BackgroundTasks，由路由通过依赖注入得到；
    - func：Callable，要执行的任务函数（如 vectorize_and_store）；
    - *args：传给 func 的位置参数；
    - **kwargs：传给 func 的关键字参数。

    返回值：无返回值。

    关键逻辑：调用 background_tasks.add_task(func, *args, **kwargs)，由框架在响应发送后执行任务。
    """
    background_tasks.add_task(func, *args, **kwargs)
