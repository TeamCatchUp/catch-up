from __future__ import annotations

from dataclasses import dataclass

import pytest

from catchup.sync.backfill.sequential_v2 import SequentialBackfillSpec
from catchup.sync.backfill.sequential_v2 import run_sequential_v2_backfill


@dataclass(slots=True, frozen=True)
class _Result:
    scanned: int
    succeeded: int
    skipped: int
    failed: int


class _Service:
    def __init__(self, results: list[_Result]) -> None:
        self._results = results
        self.calls: list[int] = []

    async def backfill_batch(
        self,
        *,
        limit: int,
    ) -> _Result:
        self.calls.append(limit)
        if not self._results:
            raise AssertionError("unexpected extra backfill_batch call")
        return self._results.pop(0)


def _spec(key: str, service: _Service) -> SequentialBackfillSpec:
    connector, entity_type = key.split("/")
    return SequentialBackfillSpec(
        key=key,
        connector=connector,
        entity_type=entity_type,
        service_factory=lambda: service,
    )


@pytest.mark.asyncio
async def test_sequential_backfill_completes_entity_before_next_entity() -> None:
    first = _Service(
        [
            _Result(scanned=2, succeeded=2, skipped=0, failed=0),
            _Result(scanned=0, succeeded=0, skipped=0, failed=0),
        ]
    )
    second = _Service([_Result(scanned=0, succeeded=0, skipped=0, failed=0)])

    result = await run_sequential_v2_backfill(
        [_spec("github/pr", first), _spec("slack/message", second)],
        batch_size=10,
    )

    assert result.status == "completed"
    assert result.stop_reason is None
    assert result.completed_entities == 2
    assert result.scanned == 2
    assert result.succeeded == 2
    assert first.calls == [10, 10]
    assert second.calls == [10]


@pytest.mark.asyncio
async def test_sequential_backfill_continues_after_target_failure() -> None:
    first = _Service(
        [
            _Result(scanned=1, succeeded=0, skipped=0, failed=1),
            _Result(scanned=0, succeeded=0, skipped=0, failed=0),
        ]
    )
    second = _Service([_Result(scanned=0, succeeded=0, skipped=0, failed=0)])

    result = await run_sequential_v2_backfill(
        [_spec("github/pr", first), _spec("slack/message", second)],
        batch_size=5,
    )

    assert result.status == "completed_with_failures"
    assert result.stop_reason is None
    assert result.failed == 1
    assert len(result.entities) == 2
    assert result.entities[0].status == "completed_with_failures"
    assert first.calls == [5, 5]
    assert second.calls == [5]


@pytest.mark.asyncio
async def test_sequential_backfill_stops_before_next_entity_on_no_progress() -> None:
    first = _Service(
        [
            _Result(scanned=3, succeeded=0, skipped=3, failed=0),
            _Result(scanned=3, succeeded=0, skipped=3, failed=0),
        ]
    )
    second = _Service([_Result(scanned=0, succeeded=0, skipped=0, failed=0)])

    result = await run_sequential_v2_backfill(
        [_spec("github/pr", first), _spec("slack/message", second)],
        batch_size=5,
    )

    assert result.status == "stopped"
    assert result.stop_reason == "no_progress"
    assert result.skipped == 6
    assert result.entities[0].status == "blocked"
    assert second.calls == []


@pytest.mark.asyncio
async def test_sequential_backfill_stops_when_scanned_batches_make_no_progress() -> None:
    first = _Service(
        [
            _Result(scanned=1, succeeded=0, skipped=0, failed=0),
            _Result(scanned=1, succeeded=0, skipped=0, failed=0),
        ]
    )
    second = _Service([_Result(scanned=0, succeeded=0, skipped=0, failed=0)])

    result = await run_sequential_v2_backfill(
        [_spec("github/pr", first), _spec("slack/message", second)],
        batch_size=5,
    )

    assert result.status == "stopped"
    assert result.stop_reason == "no_progress"
    assert result.scanned == 2
    assert result.succeeded == 0
    assert result.failed == 0
    assert result.skipped == 0
    assert result.entities[0].status == "blocked"
    assert first.calls == [5, 5]
    assert second.calls == []


@pytest.mark.asyncio
async def test_sequential_backfill_summary_aggregates_batches() -> None:
    first = _Service(
        [
            _Result(scanned=2, succeeded=1, skipped=1, failed=0),
            _Result(scanned=1, succeeded=1, skipped=0, failed=0),
            _Result(scanned=0, succeeded=0, skipped=0, failed=0),
        ]
    )

    result = await run_sequential_v2_backfill(
        [_spec("github/pr", first)],
        batch_size=7,
    )

    assert result.status == "completed"
    assert result.scanned == 3
    assert result.succeeded == 2
    assert result.skipped == 1
    assert result.failed == 0
    assert result.entities[0].batches == 3


class _ExplodingService:
    def __init__(self) -> None:
        self.calls = 0

    async def backfill_batch(
        self,
        *,
        limit: int,
    ) -> _Result:
        del limit
        self.calls += 1
        raise RuntimeError("database unavailable")


@pytest.mark.asyncio
async def test_sequential_backfill_stops_on_service_level_exception() -> None:
    first = _ExplodingService()
    second = _Service([_Result(scanned=0, succeeded=0, skipped=0, failed=0)])

    result = await run_sequential_v2_backfill(
        [_spec("github/pr", first), _spec("slack/message", second)],
        batch_size=5,
    )

    assert result.status == "stopped"
    assert result.stop_reason == "exception"
    assert result.entities[0].status == "failed"
    assert first.calls == 1
    assert second.calls == []
