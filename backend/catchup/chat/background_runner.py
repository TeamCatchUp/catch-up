from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger()

_tasks: dict[str, asyncio.Task] = {}


class ChatBackgroundRunner:
    """채팅 백그라운드 태스크를 관리한다."""

    def is_running(self, session_id: uuid.UUID) -> bool:
        """해당 세션의 태스크가 실행 중인지 확인한다."""
        task = _tasks.get(str(session_id))
        return task is not None and not task.done()

    async def ensure_running(
        self,
        session_id: uuid.UUID,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """태스크가 없으면 생성한다. 이미 실행 중이면 no-op이다."""
        if self.is_running(session_id):
            logger.info("background_task_already_running", session_id=str(session_id))
            return

        key = str(session_id)
        task = asyncio.create_task(coro_factory(), name=f"chat-{key}")
        _tasks[key] = task
        task.add_done_callback(lambda _: _tasks.pop(key, None))
        logger.info("background_task_started", session_id=key)
        await asyncio.sleep(0)

    async def cancel(self, session_id: uuid.UUID) -> None:
        """태스크를 취소하고 완료를 기다린다."""
        key = str(session_id)
        task = _tasks.get(key)
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        logger.info("background_task_cancelled", session_id=key)


_runner = ChatBackgroundRunner()


def get_background_runner() -> ChatBackgroundRunner:
    """모듈 레벨 싱글턴을 반환한다."""
    return _runner
