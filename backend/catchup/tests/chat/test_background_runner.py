import asyncio
import uuid

import pytest

from catchup.chat.background_runner import ChatBackgroundRunner
from catchup.chat.background_runner import _tasks


@pytest.fixture(autouse=True)
def clear_task_registry():
    _tasks.clear()
    yield
    _tasks.clear()


@pytest.mark.asyncio
async def test_ensure_running_starts_task():
    runner = ChatBackgroundRunner()
    session_id = uuid.uuid4()
    completed = asyncio.Event()

    async def dummy():
        completed.set()

    await runner.ensure_running(session_id, lambda: dummy())
    await asyncio.wait_for(completed.wait(), timeout=1.0)
    # 태스크 완료 후 레지스트리에서 제거됨
    assert not runner.is_running(session_id)


@pytest.mark.asyncio
async def test_ensure_running_deduplicates():
    runner = ChatBackgroundRunner()
    session_id = uuid.uuid4()
    started = 0

    ready = asyncio.Event()

    async def slow():
        nonlocal started
        started += 1
        await ready.wait()

    await runner.ensure_running(session_id, lambda: slow())
    await runner.ensure_running(session_id, lambda: slow())  # 두 번째는 no-op

    assert started == 1
    assert runner.is_running(session_id)
    ready.set()


@pytest.mark.asyncio
async def test_cancel_stops_running_task():
    runner = ChatBackgroundRunner()
    session_id = uuid.uuid4()
    cancelled = False

    async def long_running():
        nonlocal cancelled
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled = True
            raise

    await runner.ensure_running(session_id, lambda: long_running())
    assert runner.is_running(session_id)

    await runner.cancel(session_id)
    assert not runner.is_running(session_id)
    assert cancelled
