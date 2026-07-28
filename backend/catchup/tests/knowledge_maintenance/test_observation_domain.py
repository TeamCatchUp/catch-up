from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind


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
