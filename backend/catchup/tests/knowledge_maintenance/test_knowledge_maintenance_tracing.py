from __future__ import annotations

import re
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import pytest

from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (
    CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (
    ChannelTalkUserChatNormalizer,
)
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.observability import tracing
from catchup.knowledge_maintenance.observability import tracing_decorators
from catchup.knowledge_maintenance.observability.tracing import user_chat_trace_id
from catchup.knowledge_maintenance.observability.tracing_decorators import trace_extract

# Langfuse SDK가 요구하는 trace id 형식이다. 이 규칙을 벗어난 값을 넘기면
# SDK 내부의 `int(trace_id, 16)`이 ValueError로 끊긴다.
_LANGFUSE_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "channel_talk"
NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)


class _FakeSpan:
    def __init__(self) -> None:
        self.outputs: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> None:
        self.outputs.append(kwargs)


class _FakeSpanContext:
    def __init__(self, span: _FakeSpan, *, fail_on_enter: bool) -> None:
        self._span = span
        self._fail_on_enter = fail_on_enter
        self.exit_exc_type: type[BaseException] | None = None

    def __enter__(self) -> _FakeSpan:
        if self._fail_on_enter:
            raise RuntimeError("span enter failed")
        return self._span

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.exit_exc_type = exc_type
        return False


class _FakeClient:
    """start_as_current_observation만 흉내내는 최소 대역이다."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self._fail_on = fail_on
        self.calls: list[dict[str, Any]] = []
        self.span = _FakeSpan()
        self.contexts: list[_FakeSpanContext] = []

    def start_as_current_observation(self, **kwargs: Any) -> _FakeSpanContext:
        self.calls.append(kwargs)
        if self._fail_on == "open":
            raise ValueError("span open failed")
        context = _FakeSpanContext(self.span, fail_on_enter=self._fail_on == "enter")
        self.contexts.append(context)
        return context


class _RecordingExtractor:
    def __init__(self) -> None:
        self.invoke_configs: list[Any] = []

    @trace_extract
    async def extract(
        self,
        request: KnowledgeExtractionRequest,
        *,
        invoke_config: dict[str, Any] | None = None,
    ) -> KnowledgeCandidateBatch:
        self.invoke_configs.append(invoke_config)
        return KnowledgeCandidateBatch()


def _request(**overrides: object) -> KnowledgeExtractionRequest:
    values: dict[str, object] = {
        "content": "결제 기능은 9월 출시 예정이다.",
        "source_type": "channel_talk",
        "contract_version": "1",
        "workspace_id": 1,
        "external_document_id": "ct-eval-008",
    }
    values.update(overrides)
    return KnowledgeExtractionRequest.model_validate(values)


def _use_client(monkeypatch: pytest.MonkeyPatch, client: Any) -> None:
    monkeypatch.setattr(tracing_decorators, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(tracing, "get_langfuse_client", lambda: client)


def test_trace_id_is_accepted_by_langfuse() -> None:
    trace_id = user_chat_trace_id(workspace_id=1, external_document_id="ct-eval-008")

    assert _LANGFUSE_TRACE_ID.match(trace_id)
    # Langfuse가 trace id를 정수로 되돌리는 지점이다. 하이픈이 섞이면 여기서 깨진다.
    assert int(trace_id, 16) > 0


def test_trace_id_is_deterministic_per_user_chat() -> None:
    first = user_chat_trace_id(workspace_id=1, external_document_id="ct-eval-008")
    second = user_chat_trace_id(workspace_id=1, external_document_id="ct-eval-008")
    other_workspace = user_chat_trace_id(
        workspace_id=2, external_document_id="ct-eval-008"
    )
    other_document = user_chat_trace_id(
        workspace_id=1, external_document_id="ct-eval-011"
    )

    assert first == second
    assert first != other_workspace
    assert first != other_document


def test_invoke_config_refuses_trace_id_langfuse_cannot_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_client(monkeypatch, _FakeClient())

    assert tracing.llm_invoke_config("not-a-langfuse-trace-id") == {}


def test_invoke_config_is_empty_without_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_client(monkeypatch, None)

    assert tracing.llm_invoke_config(
        user_chat_trace_id(workspace_id=1, external_document_id="ct-eval-008")
    ) == {}


@pytest.mark.asyncio
async def test_extract_opens_span_on_the_user_chat_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient()
    _use_client(monkeypatch, client)
    extractor = _RecordingExtractor()

    batch = await extractor.extract(_request())

    assert isinstance(batch, KnowledgeCandidateBatch)
    assert client.calls[0]["name"] == "extract"
    assert client.calls[0]["trace_context"] == {
        "trace_id": user_chat_trace_id(
            workspace_id=1, external_document_id="ct-eval-008"
        )
    }
    assert client.span.outputs


@pytest.mark.asyncio
async def test_extract_survives_span_open_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_client(monkeypatch, _FakeClient(fail_on="open"))
    extractor = _RecordingExtractor()

    assert isinstance(await extractor.extract(_request()), KnowledgeCandidateBatch)


@pytest.mark.asyncio
async def test_extract_survives_span_enter_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Langfuse는 `__enter__`에서 입력을 직렬화한다. 그 실패도 삼켜야 한다."""
    _use_client(monkeypatch, _FakeClient(fail_on="enter"))
    extractor = _RecordingExtractor()

    assert isinstance(await extractor.extract(_request()), KnowledgeCandidateBatch)


@pytest.mark.asyncio
async def test_extract_reports_caller_failure_to_the_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient()
    _use_client(monkeypatch, client)

    class ExtractionFailed(RuntimeError):
        pass

    class _FailingExtractor:
        @trace_extract
        async def extract(
            self,
            request: KnowledgeExtractionRequest,
            *,
            invoke_config: dict[str, Any] | None = None,
        ) -> KnowledgeCandidateBatch:
            raise ExtractionFailed("llm down")

    with pytest.raises(ExtractionFailed):
        await _FailingExtractor().extract(_request())

    assert client.contexts[0].exit_exc_type is ExtractionFailed


@pytest.mark.asyncio
async def test_extract_skips_tracing_without_document_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient()
    _use_client(monkeypatch, client)
    extractor = _RecordingExtractor()

    await extractor.extract(_request(external_document_id=None))

    assert client.calls == []
    assert extractor.invoke_configs == [None]


def _source_version(key: str) -> SourceVersion:
    return SourceVersion(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        workspace_id=1,
        source_type="channel_talk",
        source_identity=SourceIdentity(
            entity_type="user_chat",
            scope_id="ch-catchup-eval",
            target_id="ch-catchup-eval",
            external_document_id=key,
        ),
        change_kind=ChangeKind.CREATED,
        source_version_key="1",
        title=None,
        canonical_url=None,
        content=(FIXTURE_DIR / f"{key}.json").read_text(encoding="utf-8"),
        content_type=CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
        content_hash=None,
        source_updated_at=None,
        observed_at=NOW,
        idempotency_key="idem-1",
        payload_hash="ph-1",
        metadata={},
        created_at=NOW,
    )


def test_normalize_shares_the_trace_with_extract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """두 단계가 하나의 Trace로 합쳐지는 것이 이 기능의 목적이다."""
    client = _FakeClient()
    _use_client(monkeypatch, client)

    observation = ChannelTalkUserChatNormalizer().normalize(
        _source_version("ct-eval-008")
    )

    assert observation.content is not None
    assert client.calls[0]["name"] == "normalize"
    assert client.calls[0]["trace_context"] == {
        "trace_id": user_chat_trace_id(
            workspace_id=1, external_document_id="ct-eval-008"
        )
    }


def test_normalize_survives_span_enter_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_client(monkeypatch, _FakeClient(fail_on="enter"))

    observation = ChannelTalkUserChatNormalizer().normalize(
        _source_version("ct-eval-008")
    )

    assert observation.content is not None
