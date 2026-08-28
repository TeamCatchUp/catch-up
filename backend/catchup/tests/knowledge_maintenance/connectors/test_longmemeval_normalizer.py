from __future__ import annotations

import dataclasses
import json
import re
import uuid
from datetime import datetime
from datetime import timezone

import pytest

from catchup.evaluation.longmemeval.dataset import OracleSession
from catchup.evaluation.longmemeval.dataset import OracleTurn
from catchup.evaluation.longmemeval.run_ingestion import session_envelope
from catchup.knowledge_maintenance.adapters.connectors.longmemeval.observation_normalizer import (  # noqa: E501
    LONGMEMEVAL_SESSION_MEDIA_TYPE,
)
from catchup.knowledge_maintenance.adapters.connectors.longmemeval.observation_normalizer import (  # noqa: E501
    LongMemEvalSessionNormalizer,
)
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion

NOW = datetime(2026, 8, 4, 9, 0, tzinfo=timezone.utc)
SESSION_AT = datetime(2023, 4, 10, 23, 7, tzinfo=timezone.utc)

# 발화 줄 앞에 붙는 발화 시각이다.
_UTTERANCE_STAMP = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] ")


def _session() -> OracleSession:
    return OracleSession(
        session_id="answer_e1f2",
        timestamp=SESSION_AT,
        turns=(
            OracleTurn(
                role="user",
                content="I switched my daily driver to a road bike.",
                has_answer=True,
            ),
            OracleTurn(
                role="assistant",
                content="Nice — how is the commute going?",
                has_answer=False,
            ),
        ),
    )


def _content(session: OracleSession) -> str:
    return json.dumps(
        {
            "session_id": session.session_id,
            "timestamp": session.timestamp.isoformat(),
            "turns": [
                {"role": turn.role, "content": turn.content}
                for turn in session.turns
            ],
        },
        ensure_ascii=False,
    )


def _source_version(session: OracleSession) -> SourceVersion:
    return SourceVersion(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        workspace_id=902,
        source_type="longmemeval",
        source_identity=SourceIdentity(
            entity_type="session",
            scope_id="longmemeval",
            target_id="longmemeval",
            external_document_id=session.session_id,
        ),
        change_kind=ChangeKind.CREATED,
        source_version_key="1",
        title=None,
        canonical_url=None,
        content=_content(session),
        content_type=LONGMEMEVAL_SESSION_MEDIA_TYPE,
        content_hash="a" * 64,
        source_updated_at=SESSION_AT,
        observed_at=NOW,
        idempotency_key=f"{session.session_id}-1",
        payload_hash="b" * 64,
        metadata={},
        created_at=NOW,
    )


@pytest.fixture
def normalizer() -> LongMemEvalSessionNormalizer:
    return LongMemEvalSessionNormalizer()


def test_every_line_carries_the_session_time_and_role(normalizer) -> None:
    """본문의 모든 줄은 세션 시각과 역할 접두사로 시작한다."""
    observation = normalizer.normalize(_source_version(_session()))

    assert observation.observation_kind == ObservationKind.DOCUMENT
    assert observation.content is not None
    lines = observation.content.split("\n")
    assert len(lines) == 2
    assert lines[0] == (
        "[2023-04-10 23:07] user: "
        "I switched my daily driver to a road bike."
    )
    assert lines[1] == (
        "[2023-04-10 23:07] assistant: Nice — how is the commute going?"
    )
    for line in lines:
        assert _UTTERANCE_STAMP.match(line)


def test_utterance_spans_slice_back_to_their_line(normalizer) -> None:
    """구간을 본문에 그대로 대입하면 그 발화 줄이 다시 나온다."""
    observation = normalizer.normalize(_source_version(_session()))

    content = observation.content
    assert content is not None
    spans = observation.source_attributes["utterance_spans"]
    assert len(spans) == 2

    lines = content.split("\n")
    for span, line in zip(spans, lines, strict=True):
        assert content[span["start"] : span["end"]] == line
        assert span["at"] == SESSION_AT.isoformat()

    assert spans[0]["end"] < spans[1]["start"]


def test_multiline_turn_stays_in_one_span(normalizer) -> None:
    """턴 본문에 개행이 있어도 구간은 그 턴 전체를 가리킨다.

    실제 데이터의 assistant 턴에는 목록이 자주 들어 있어 개행이 흔하다.
    본문을 줄 단위로 세면 구간이 어긋나므로 code point로만 센다.
    """
    session = dataclasses.replace(
        _session(),
        turns=(
            OracleTurn(
                role="assistant",
                content="Two tips:\n1. Fit first.\n2. Then gearing.",
                has_answer=False,
            ),
            OracleTurn(role="user", content="Got it.", has_answer=False),
        ),
    )
    observation = normalizer.normalize(_source_version(session))

    content = observation.content
    assert content is not None
    spans = observation.source_attributes["utterance_spans"]
    assert len(spans) == 2
    assert content[spans[0]["start"] : spans[0]["end"]] == (
        "[2023-04-10 23:07] assistant: "
        "Two tips:\n1. Fit first.\n2. Then gearing."
    )
    assert content[spans[1]["start"] : spans[1]["end"]] == (
        "[2023-04-10 23:07] user: Got it."
    )


def test_blank_turn_leaves_no_span(normalizer) -> None:
    """빈 턴은 본문에도 구간에도 남기지 않는다."""
    session = dataclasses.replace(
        _session(),
        turns=(
            OracleTurn(role="user", content="   ", has_answer=False),
            OracleTurn(role="assistant", content="Sure.", has_answer=False),
        ),
    )
    observation = normalizer.normalize(_source_version(session))

    assert observation.content == "[2023-04-10 23:07] assistant: Sure."
    spans = observation.source_attributes["utterance_spans"]
    assert len(spans) == 1
    assert spans[0]["start"] == 0


def test_occurred_at_is_the_session_time(normalizer) -> None:
    """세션 시각이 곧 관찰 시각이다."""
    observation = normalizer.normalize(_source_version(_session()))

    assert observation.occurred_at == SESSION_AT
    assert observation.source_attributes["session_id"] == "answer_e1f2"
    assert observation.source_attributes["turn_count"] == 2


def test_normalize_is_deterministic(normalizer) -> None:
    """같은 입력을 두 번 넣으면 같은 결과가 나온다."""
    first = normalizer.normalize(_source_version(_session()))
    second = normalizer.normalize(_source_version(_session()))

    assert first.content == second.content
    assert first.content_hash == second.content_hash
    assert first.content_hash == content_hash(first.content or "")
    assert dict(first.source_attributes) == dict(second.source_attributes)


def test_unexpected_media_type_is_rejected(normalizer) -> None:
    """다른 media type은 정규화하지 않는다."""
    source_version = dataclasses.replace(
        _source_version(_session()),
        content_type="text/plain",
    )
    with pytest.raises(ValueError):
        normalizer.normalize(source_version)


def test_session_envelope_is_replay_safe() -> None:
    """같은 세션으로 만든 envelope는 늘 같은 idempotency key를 쓴다."""
    session = _session()
    first = session_envelope(session, workspace_id=902)
    second = session_envelope(session, workspace_id=902)

    assert first.source_type == "longmemeval"
    assert first.workspace_id == 902
    assert first.source_identity.external_document_id == "answer_e1f2"
    assert first.idempotency_key == "answer_e1f2-1"
    assert first.observed_at == SESSION_AT
    assert first.content_type == LONGMEMEVAL_SESSION_MEDIA_TYPE
    assert first.change_kind == ChangeKind.CREATED
    assert first.idempotency_key == second.idempotency_key
    assert first.content == second.content


def test_session_envelope_content_feeds_the_normalizer() -> None:
    """envelope 본문은 normalizer가 그대로 읽을 수 있는 JSON이다."""
    session = _session()
    envelope = session_envelope(session, workspace_id=902)

    payload = json.loads(envelope.content or "")
    assert payload["session_id"] == "answer_e1f2"
    assert payload["timestamp"] == SESSION_AT.isoformat()
    assert [turn["role"] for turn in payload["turns"]] == [
        "user",
        "assistant",
    ]
