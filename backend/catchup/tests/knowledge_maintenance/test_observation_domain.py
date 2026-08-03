from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import utterance_event_at


def _observation(**overrides: object) -> NormalizedObservation:
    values: dict[str, object] = {
        "normalizer_id": "channel_talk.user_chat",
        "normalizer_version": "1",
        "observation_kind": ObservationKind.DOCUMENT,
        "content": "결제 기능은 9월 출시 예정이다.",
        "content_hash": "a" * 64,
    }
    values.update(overrides)
    return NormalizedObservation(**values)  # type: ignore[arg-type]


def test_tombstone_observation_rejects_content() -> None:
    with pytest.raises(ValueError):
        _observation(
            observation_kind=ObservationKind.TOMBSTONE,
            content="삭제된 원문에는 본문이 없어야 한다",
        )


def test_document_observation_requires_content() -> None:
    with pytest.raises(ValueError):
        _observation(content=None, content_hash=None)


def test_occurred_at_must_include_timezone() -> None:
    with pytest.raises(ValueError):
        _observation(occurred_at=datetime(2026, 7, 28, 9, 0))


def test_occurred_at_is_normalized_to_utc() -> None:
    seoul = timezone(timedelta(hours=9))

    observation = _observation(
        occurred_at=datetime(2026, 7, 28, 18, 0, tzinfo=seoul),
    )

    assert observation.occurred_at == datetime(
        2026, 7, 28, 9, 0, tzinfo=timezone.utc
    )


def test_observation_is_immutable_after_creation() -> None:
    observation = _observation(
        source_attributes={"state": "closed"},
        metadata_entities=(
            MetadataEntity(
                entity_type="customer",
                external_key="user-1",
                display_name="예시고객사",
            ),
        ),
    )

    with pytest.raises(TypeError):
        observation.source_attributes["state"] = "opened"

    assert observation.metadata_entities[0].display_name == "예시고객사"


def test_metadata_entity_rejects_blank_display_name() -> None:
    with pytest.raises(ValueError):
        MetadataEntity(
            entity_type="customer",
            external_key="user-1",
            display_name="  ",
        )


def _spans() -> dict[str, object]:
    return {
        "utterance_spans": [
            {"start": 0, "end": 10, "at": "2026-08-01T10:00:00+00:00"},
            {"start": 11, "end": 25, "at": "2026-08-10T11:30:00+00:00"},
        ]
    }


def test_utterance_event_at_picks_the_span_that_contains_the_offset() -> None:
    """근거 위치가 든 발화의 시각을 고른다."""
    assert utterance_event_at(_spans(), 0) == "2026-08-01T10:00:00+00:00"
    assert utterance_event_at(_spans(), 9) == "2026-08-01T10:00:00+00:00"
    assert utterance_event_at(_spans(), 11) == "2026-08-10T11:30:00+00:00"


def test_utterance_event_at_is_empty_outside_every_span() -> None:
    """구간 밖이면 시각을 지어내지 않는다."""
    assert utterance_event_at(_spans(), 10) is None
    assert utterance_event_at(_spans(), 999) is None
    assert utterance_event_at({}, 0) is None
