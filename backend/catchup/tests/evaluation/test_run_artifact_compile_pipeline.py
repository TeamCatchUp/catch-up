"""카드 컴파일 러너의 정의 고르기를 확인한다.

러너는 정의 하나만 돌려 볼 수 있어야 한다. 그 고르기를 컴파일 서비스에
인자로 두면 "workspace의 정의를 전부 돈다"는 계약이 무너지므로, 러너가
UnitOfWork를 감싸 정의 목록을 가린다. 그 가림막이 정의만 가리고 나머지
저장소와 transaction 경계는 그대로 통과시키는지 못 박는다.

DB도 LLM도 부르지 않는다.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Sequence
from typing import Any

import pytest

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.evaluation import run_artifact_compile_pipeline as runner
from catchup.evaluation.run_artifact_compile_pipeline import only_definition
from catchup.knowledge_maintenance.adapters.llm.block_narrator import LlmBlockNarrator
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpec
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    StoredArtifactDefinition,
)
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    ArtifactCompileResult,
)

FIRST_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
SECOND_ID = uuid.UUID("ffffffff-0000-4000-8000-000000000002")


def _definition(definition_id: uuid.UUID) -> StoredArtifactDefinition:
    """정의 한 줄을 만든다. 여기서 보는 것은 식별자뿐이다."""
    return StoredArtifactDefinition(
        id=definition_id,
        channel_id=uuid.uuid4(),
        kind="entity_summary",
        selection_spec=SelectionSpec(
            entity_types=("feature_request",),
            relation_paths=(),
            predicate_sections=None,
        ),
        title_prefix="entity_summary",
    )


class _FakeDefinitionRepository:
    """정의 목록을 그대로 돌려주는 저장소를 대신한다."""

    def __init__(self, definitions: tuple[StoredArtifactDefinition, ...]):
        self.definitions = definitions
        self.style_calls: list[uuid.UUID] = []
        self.purpose_calls: list[uuid.UUID] = []

    def list_definitions(self) -> tuple[StoredArtifactDefinition, ...]:
        return self.definitions

    def find_channel_style(self, *, channel_id: uuid.UUID) -> str | None:
        self.style_calls.append(channel_id)
        return "style.faq"

    def find_channel_purpose(self, *, channel_id: uuid.UUID) -> str | None:
        self.purpose_calls.append(channel_id)
        return "voc.top_requests"


class _FakeUnitOfWork:
    """저장소 몇 개와 transaction 경계만 갖춘 UnitOfWork를 대신한다.

    실제 UnitOfWork는 저장소를 `__enter__`에서 만든다. 감싸는 쪽이 그
    시점을 앞질러 저장소를 붙들면 실행 때 없는 것을 잡으므로, fake도
    같은 시점에 붙인다.
    """

    def __init__(self, definitions: tuple[StoredArtifactDefinition, ...]):
        self._definitions = definitions
        self.artifacts = object()
        self.entered = 0
        self.exited = 0
        self.committed = 0

    def __enter__(self) -> _FakeUnitOfWork:
        self.entered += 1
        self.artifact_definitions = _FakeDefinitionRepository(
            self._definitions
        )
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.exited += 1

    def commit(self) -> None:
        self.committed += 1


def test_only_the_chosen_definition_is_listed() -> None:
    """고른 정의 하나만 컴파일 입구에 보인다."""
    inner = _FakeUnitOfWork((_definition(FIRST_ID), _definition(SECOND_ID)))
    wrapped = only_definition(inner, SECOND_ID)

    with wrapped:
        listed = wrapped.artifact_definitions.list_definitions()

    assert [item.id for item in listed] == [SECOND_ID]


def test_unknown_definition_id_lists_nothing() -> None:
    """없는 식별자를 고르면 빈 목록이다.

    엉뚱한 정의를 대신 돌리는 것보다 아무것도 하지 않는 편이 낫다.
    """
    inner = _FakeUnitOfWork((_definition(FIRST_ID),))
    wrapped = only_definition(inner, SECOND_ID)

    with wrapped:
        assert wrapped.artifact_definitions.list_definitions() == ()


def test_other_repositories_and_boundary_pass_through() -> None:
    """정의 말고는 감싸지 않고 그대로 통과시킨다."""
    inner = _FakeUnitOfWork((_definition(FIRST_ID),))
    wrapped = only_definition(inner, FIRST_ID)

    with wrapped:
        assert wrapped.artifacts is inner.artifacts
        wrapped.commit()

    assert inner.entered == 1
    assert inner.exited == 1
    assert inner.committed == 1


def test_channel_style_lookup_passes_through() -> None:
    """문체 조회는 가림막을 지나 감싼 저장소에 그대로 닿는다.

    산문을 쓰려면 채널 문체를 읽어야 한다. 가림막이 그 조회를 넘기지
    않으면 --definition-id로 돌린 실행만 서술 자리에서 터진다.
    """
    inner = _FakeUnitOfWork((_definition(FIRST_ID),))
    wrapped = only_definition(inner, FIRST_ID)
    channel_id = uuid.uuid4()

    with wrapped:
        found = wrapped.artifact_definitions.find_channel_style(
            channel_id=channel_id
        )
        assert inner.artifact_definitions.style_calls == [channel_id]

    assert found == "style.faq"


def test_channel_purpose_lookup_passes_through() -> None:
    """목적 조회도 가림막을 지나 감싼 저장소에 그대로 닿는다.

    목적 문장은 채널이 고른 목적에서 나온다. 가림막이 이 조회를 넘기지
    않으면 --definition-id로 돌린 실행만 목적 없는 문장을 쓴다.
    """
    inner = _FakeUnitOfWork((_definition(FIRST_ID),))
    wrapped = only_definition(inner, FIRST_ID)
    channel_id = uuid.uuid4()

    with wrapped:
        found = wrapped.artifact_definitions.find_channel_purpose(
            channel_id=channel_id
        )
        assert inner.artifact_definitions.purpose_calls == [channel_id]

    assert found == "voc.top_requests"


class _FakeEngine:
    """engine을 대신한다. 닫혔는지만 기억한다."""

    def __init__(self) -> None:
        self.disposed = 0

    def dispose(self) -> None:
        self.disposed += 1


class _FakeRunUnitOfWork:
    """러너가 여닫기만 하는 UnitOfWork를 대신한다."""

    def __enter__(self) -> _FakeRunUnitOfWork:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        return None


def _stub_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: ArtifactCompileResult,
    extra_args: Sequence[str] = (),
) -> _FakeEngine:
    """DB와 컴파일을 대신 세워 main을 부를 수 있게 만든다."""
    engine = _FakeEngine()
    monkeypatch.setattr(runner, "create_engine", lambda url: engine)
    monkeypatch.setattr(runner, "sessionmaker", lambda **kwargs: object())
    monkeypatch.setattr(
        runner,
        "KnowledgeMaintenanceUnitOfWork",
        lambda *args, **kwargs: _FakeRunUnitOfWork(),
    )
    monkeypatch.setattr(
        runner,
        "_load_vocabulary",
        lambda *args, **kwargs: ExtractionVocabulary(
            snapshot_id="1",
            predicate_entries=(
                PredicateEntry(
                    name="status", definition="지금 상태다.", value_type="text"
                ),
            ),
        ),
    )
    monkeypatch.setattr(
        runner, "compile_definition_artifacts", lambda *a, **kw: result
    )
    monkeypatch.setattr(runner, "_print_pending_cards", lambda uow: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run",
            "--workspace-id",
            "1",
            "--ontology-version",
            "1",
            *extra_args,
        ],
    )
    return engine


def test_failed_nodes_are_printed_and_exit_code_is_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """접힌 노드가 있으면 결과에 적히고 종료 코드가 1이다.

    이 러너가 지금 유일한 실행 입구다. 조용히 0으로 끝나면 문서가 빠진
    실행을 사람도 자동화도 성공으로 기록한다.
    """
    engine = _stub_run(
        monkeypatch,
        result=ArtifactCompileResult(
            definitions_considered=1,
            nodes_considered=2,
            proposals_created=1,
            nodes_failed=1,
        ),
    )

    code = runner.main()

    assert code == 1
    assert "실패 노드 1" in capsys.readouterr().out
    assert engine.disposed == 1


def test_clean_run_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """접힌 노드가 없으면 종료 코드가 0이다."""
    _stub_run(
        monkeypatch,
        result=ArtifactCompileResult(
            definitions_considered=1,
            nodes_considered=2,
            proposals_created=2,
        ),
    )

    code = runner.main()

    assert code == 0
    assert "실패 노드 0" in capsys.readouterr().out


def test_zero_definitions_still_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """정의가 없는 실행은 그대로 0으로 끝난다.

    정의가 없는 것은 아직 걸어 두지 않았다는 뜻이지 문서가 빠진 실행이
    아니다. 종료 코드를 움직이는 것은 접힌 노드뿐이다.
    """
    _stub_run(monkeypatch, result=ArtifactCompileResult())

    code = runner.main()

    assert code == 0
    assert "읽은 정의가 없다" in capsys.readouterr().out


class _FakeChatModel:
    """구조화 출력만 흉내 내는 모델을 대신한다."""

    def with_structured_output(self, *args: Any, **kwargs: Any) -> object:
        return object()


class _FakeLlmService:
    """LLM 서비스를 대신한다. 모델 자리만 채운다."""

    def get_llm(self) -> _FakeChatModel:
        return _FakeChatModel()


def test_no_narrate_builds_no_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--no-narrate면 LLM 서비스를 만들지 않고 narrator도 없다."""
    factory_calls: list[dict[str, Any]] = []
    compile_calls: list[dict[str, Any]] = []

    def _fake_factory(**kwargs: Any) -> _FakeLlmService:
        factory_calls.append(kwargs)
        return _FakeLlmService()

    def _fake_compile(uow: Any, **kwargs: Any) -> ArtifactCompileResult:
        compile_calls.append(kwargs)
        return ArtifactCompileResult()

    _stub_run(
        monkeypatch,
        result=ArtifactCompileResult(),
        extra_args=["--no-narrate"],
    )
    monkeypatch.setattr(runner, "get_llm_service", _fake_factory)
    monkeypatch.setattr(runner, "compile_definition_artifacts", _fake_compile)

    assert runner.main() == 0
    assert factory_calls == []
    assert compile_calls[0]["narrator"] is None


def test_capacity_reaches_the_llm_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--capacity가 모델 등급으로 그대로 넘어간다."""
    factory_calls: list[dict[str, Any]] = []
    compile_calls: list[dict[str, Any]] = []

    def _fake_factory(**kwargs: Any) -> _FakeLlmService:
        factory_calls.append(kwargs)
        return _FakeLlmService()

    def _fake_compile(uow: Any, **kwargs: Any) -> ArtifactCompileResult:
        compile_calls.append(kwargs)
        return ArtifactCompileResult()

    _stub_run(
        monkeypatch,
        result=ArtifactCompileResult(),
        extra_args=["--capacity", "small"],
    )
    monkeypatch.setattr(runner, "get_llm_service", _fake_factory)
    monkeypatch.setattr(runner, "compile_definition_artifacts", _fake_compile)

    assert runner.main() == 0
    assert factory_calls[0]["provider"] is LlmProvider.AWS_BEDROCK
    assert factory_calls[0]["model_capacity"] is ModelCapacity.SMALL
    assert isinstance(compile_calls[0]["narrator"], LlmBlockNarrator)


def test_prints_narration_counts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """서술·재사용 블록 수를 결과에 적는다."""
    _stub_run(
        monkeypatch,
        result=ArtifactCompileResult(
            definitions_considered=1,
            nodes_considered=1,
            proposals_created=1,
            blocks_narrated=3,
            blocks_narrative_reused=5,
        ),
        extra_args=["--no-narrate"],
    )

    assert runner.main() == 0
    printed = capsys.readouterr().out
    assert "산문 서술 3" in printed
    assert "재사용 5" in printed


def test_capacity_with_no_narrate_is_reported_as_ignored(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--no-narrate와 함께 준 --capacity는 무시한다고 알린다."""
    _stub_run(
        monkeypatch,
        result=ArtifactCompileResult(),
        extra_args=["--no-narrate", "--capacity", "small"],
    )

    assert runner.main() == 0
    printed = capsys.readouterr().out
    assert "--capacity small는 무시한다" in printed


def test_capacity_is_not_reported_without_no_narrate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--no-narrate만 주면 무시 안내를 적지 않는다."""
    _stub_run(
        monkeypatch,
        result=ArtifactCompileResult(),
        extra_args=["--no-narrate"],
    )

    assert runner.main() == 0
    assert "무시한다" not in capsys.readouterr().out
