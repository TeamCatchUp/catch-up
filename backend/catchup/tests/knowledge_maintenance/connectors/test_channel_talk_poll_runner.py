"""폴링 러너의 커서 안전 장벽 계산을 검증한다.

러너의 증분 커서는 저장된 원문의 최신 `source_updated_at`에서 도출된다.
그래서 수집하지 못한 대화보다 최신인 대화를 저장하면 커서가 빠진 대화를
지나쳐 다음 회차에도 집히지 않는다. 그 사고를 막는 함수가
`_split_by_barrier` 하나이므로 여기서만 직접 검증한다.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from catchup.evaluation.run_channel_talk_poll_pipeline import _split_by_barrier
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.contracts.source_change import SourceIdentityPayload
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.ports.source_poller import SkippedItem

CHANNEL_ID = "ch-catchup-eval"
NOW = datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc)


def _envelope(chat_id: str, updated_at: datetime) -> SourceChangeEnvelope:
    """장벽 판단에 쓰이는 필드만 실제 값으로 채운 envelope를 만든다."""
    version_key = str(int(updated_at.timestamp() * 1000))
    return SourceChangeEnvelope(
        schema_version=1,
        event_id=f"{chat_id}-{version_key}",
        workspace_id=1,
        source_type="channel_talk",
        source_identity=SourceIdentityPayload(
            entity_type="user_chat",
            scope_id=CHANNEL_ID,
            target_id=CHANNEL_ID,
            external_document_id=chat_id,
        ),
        change_kind=ChangeKind.UPDATED,
        source_version_key=version_key,
        title=f"{chat_id} 문의",
        canonical_url=None,
        content="{}",
        content_type="application/json",
        source_updated_at=updated_at,
        observed_at=NOW,
        idempotency_key=f"{chat_id}-{version_key}",
        metadata={},
    )


def _ids(envelopes: list[SourceChangeEnvelope]) -> list[str]:
    return [
        envelope.source_identity.external_document_id for envelope in envelopes
    ]


def test_split_by_barrier_ingests_everything_when_nothing_is_skipped() -> None:
    """빠진 대화가 없으면 장벽이 없으므로 전부 넣는다."""
    envelopes = [
        _envelope("chat-a", NOW - timedelta(hours=5)),
        _envelope("chat-b", NOW - timedelta(hours=1)),
    ]

    ingest_now, held_back = _split_by_barrier(envelopes, [])

    assert _ids(ingest_now) == ["chat-a", "chat-b"]
    assert held_back == []


def test_split_by_barrier_holds_back_envelopes_newer_than_skip() -> None:
    """빠진 대화보다 최신인 envelope만 보류한다."""
    older = _envelope("chat-older", NOW - timedelta(hours=9))
    newer = _envelope("chat-newer", NOW - timedelta(hours=1))
    skipped = [
        SkippedItem(
            item_id="chat-broken",
            ordering_marker=NOW - timedelta(hours=5),
            reason="fetch_failed",
        ),
    ]

    ingest_now, held_back = _split_by_barrier([older, newer], skipped)

    assert _ids(ingest_now) == ["chat-older"]
    assert _ids(held_back) == ["chat-newer"]


def test_split_by_barrier_uses_the_oldest_skip_as_barrier() -> None:
    """빠진 대화가 여럿이면 가장 오래된 기준 시각이 장벽이다."""
    envelopes = [
        _envelope("chat-1", NOW - timedelta(hours=9)),
        _envelope("chat-2", NOW - timedelta(hours=6)),
        _envelope("chat-3", NOW - timedelta(hours=2)),
    ]
    skipped = [
        SkippedItem(
            item_id="chat-late",
            ordering_marker=NOW - timedelta(hours=3),
            reason="fetch_failed",
        ),
        SkippedItem(
            item_id="chat-early",
            ordering_marker=NOW - timedelta(hours=8),
            reason="messages_truncated",
        ),
    ]

    ingest_now, held_back = _split_by_barrier(envelopes, skipped)

    assert _ids(ingest_now) == ["chat-1"]
    assert _ids(held_back) == ["chat-2", "chat-3"]


def test_split_by_barrier_holds_back_all_when_a_marker_is_unknown() -> None:
    """기준 시각을 모르는 빠진 대화가 있으면 전부 보류한다.

    그 대화가 창의 어디에 있는지 모르므로 어떤 envelope도 안전하다고
    증명할 수 없다.
    """
    envelopes = [
        _envelope("chat-a", NOW - timedelta(hours=9)),
        _envelope("chat-b", NOW - timedelta(hours=1)),
    ]
    skipped = [
        SkippedItem(
            item_id="chat-known",
            ordering_marker=NOW - timedelta(hours=5),
            reason="fetch_failed",
        ),
        SkippedItem(
            item_id="chat-unknown",
            ordering_marker=None,
            reason="fetch_failed",
        ),
    ]

    ingest_now, held_back = _split_by_barrier(envelopes, skipped)

    assert ingest_now == []
    assert _ids(held_back) == ["chat-a", "chat-b"]


def test_split_by_barrier_holds_back_envelope_equal_to_barrier() -> None:
    """장벽과 시각이 같은 envelope도 보류한다.

    같은 시각이면 커서가 그 지점에 도달해 빠진 대화를 덮을 수 있다.
    """
    envelopes = [_envelope("chat-tie", NOW - timedelta(hours=5))]
    skipped = [
        SkippedItem(
            item_id="chat-broken",
            ordering_marker=NOW - timedelta(hours=5),
            reason="fetch_failed",
        ),
    ]

    ingest_now, held_back = _split_by_barrier(envelopes, skipped)

    assert ingest_now == []
    assert _ids(held_back) == ["chat-tie"]
