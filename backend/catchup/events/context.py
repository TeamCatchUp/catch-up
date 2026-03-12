from contextvars import ContextVar
from fastapi import BackgroundTasks


current_bg_tasks: ContextVar[BackgroundTasks | None] = ContextVar(
    "current_bg_tasks", default=None
)
