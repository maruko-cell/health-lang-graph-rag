"""
后台任务模块：封装与上传后向量化、入库等异步任务相关的逻辑。

入参：无入参，本包仅用于导出 add_task、vectorize_and_store 等供路由使用。
返回值：无返回值。
关键逻辑：通过 add_task 将 vectorize_and_store 挂到 FastAPI BackgroundTasks，实现上传后异步入库。
"""

from app.tasks.add_task import add_task
from app.tasks.vectorize_and_store import vectorize_and_store

__all__ = ["add_task", "vectorize_and_store"]
