from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterable
from typing import TypeVar

TargetT = TypeVar("TargetT")
ResultT = TypeVar("ResultT")


async def run_bounded_targets(
    targets: Iterable[TargetT],
    *,
    concurrency: int,
    process_target: Callable[[TargetT], Awaitable[ResultT]],
) -> list[ResultT]:
    if concurrency < 1:
        raise ValueError("concurrency must be greater than 0")

    semaphore = asyncio.Semaphore(concurrency)

    async def _run(target: TargetT) -> ResultT:
        async with semaphore:
            return await process_target(target)

    return await asyncio.gather(*(_run(target) for target in targets))
