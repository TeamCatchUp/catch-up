from __future__ import annotations

import asyncio

import pytest

from catchup.sync.backfill.concurrency import run_bounded_targets


@pytest.mark.asyncio
async def test_run_bounded_targets_limits_concurrency() -> None:
    active = 0
    max_active = 0

    async def process(target: int) -> int:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return target * 2

    result = await run_bounded_targets(range(6), concurrency=3, process_target=process)

    assert result == [0, 2, 4, 6, 8, 10]
    assert max_active <= 3


@pytest.mark.asyncio
async def test_run_bounded_targets_rejects_invalid_concurrency() -> None:
    async def process(target: int) -> int:
        return target

    with pytest.raises(ValueError, match="concurrency"):
        await run_bounded_targets([1], concurrency=0, process_target=process)
