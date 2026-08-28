from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.knowledge_maintenance.domain.temporal import claim_not_closed_at
from catchup.knowledge_maintenance.domain.temporal import claim_valid_at
from catchup.knowledge_maintenance.domain.temporal import resolve_reference_time

T = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
BEFORE = datetime(2026, 7, 1, tzinfo=timezone.utc)
AFTER = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_live_claim_is_valid() -> None:
    assert claim_valid_at(BEFORE, None, T)


def test_closed_before_t_is_invalid() -> None:
    assert not claim_valid_at(BEFORE, BEFORE, T)


def test_closed_after_t_is_valid() -> None:
    assert claim_valid_at(BEFORE, AFTER, T)


def test_unknown_start_is_valid() -> None:
    # 시작 미상은 포함한다. 확실성 구분은 소비자가 valid_from으로 한다.
    assert claim_valid_at(None, None, T)
    assert not claim_valid_at(None, BEFORE, T)


def test_boundaries_are_half_open() -> None:
    # 구간은 [from, to)다. T == valid_from 참, T == valid_to 거짓.
    assert claim_valid_at(T, None, T)
    assert not claim_valid_at(BEFORE, T, T)


def test_not_yet_started_is_invalid() -> None:
    assert not claim_valid_at(AFTER, None, T)


def test_open_claim_is_not_closed() -> None:
    assert claim_not_closed_at(None, T)


def test_claim_closed_before_t_is_closed() -> None:
    assert not claim_not_closed_at(BEFORE, T)


def test_claim_closing_after_t_is_not_closed() -> None:
    assert claim_not_closed_at(AFTER, T)


def test_closing_boundary_is_half_open() -> None:
    # 구간은 [from, to)다. T == valid_to면 이미 닫힌 것으로 본다.
    assert not claim_not_closed_at(T, T)


def test_reference_time_prefers_occurred_at() -> None:
    value, source = resolve_reference_time(
        occurred_at=BEFORE, source_updated_at=T, observed_at=AFTER
    )
    assert (value, source) == (BEFORE, "occurred_at")


def test_reference_time_falls_back_to_source_updated_at() -> None:
    value, source = resolve_reference_time(
        occurred_at=None, source_updated_at=T, observed_at=AFTER
    )
    assert (value, source) == (T, "source_updated_at")


def test_reference_time_falls_back_to_observed_at() -> None:
    value, source = resolve_reference_time(
        occurred_at=None, source_updated_at=None, observed_at=AFTER
    )
    assert (value, source) == (AFTER, "observed_at")
