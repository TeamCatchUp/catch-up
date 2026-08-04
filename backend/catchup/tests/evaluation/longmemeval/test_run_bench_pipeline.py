"""manifest 소비 오케스트레이터의 순서와 중단 규칙을 못 박는다.

이 러너가 하는 일은 판단이 아니라 배선이다. 그래서 검증할 것도 배선이다
— 어느 workspace에 어느 단계를, 어떤 인자로, 어떤 순서로 부르는가. 그리고
한 단계라도 실패하면 남은 workspace를 건드리지 않는가. 실패한 workspace를
건너뛰고 이어 가면 빈 지식이 섞인 채로 점수가 나온다.

subprocess도 DB도 LLM도 부르지 않는다. 단계 실행을 주입 가능한 함수로
빼 두었기 때문에 fake로 전부 확인할 수 있다.
"""

from __future__ import annotations

import sys

import pytest

from catchup.evaluation.longmemeval.run_bench_pipeline import ADJUDICATION_MODULE
from catchup.evaluation.longmemeval.run_bench_pipeline import EXTRACTION_MODULE
from catchup.evaluation.longmemeval.run_bench_pipeline import RESOLUTION_MODULE
from catchup.evaluation.longmemeval.run_bench_pipeline import StepCommand
from catchup.evaluation.longmemeval.run_bench_pipeline import build_step_commands
from catchup.evaluation.longmemeval.run_bench_pipeline import copy_vocabulary_snapshot
from catchup.evaluation.longmemeval.run_bench_pipeline import run_pipeline
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.ports.ontology import OntologySnapshotConflict


class _Recorder:
    """단계 실행을 기록하고 정해진 exit code를 돌려주는 fake다."""

    def __init__(self, *, fail_on: tuple[int, str] | None = None) -> None:
        self.calls: list[StepCommand] = []
        self.fail_on = fail_on

    def __call__(self, command: StepCommand) -> int:
        self.calls.append(command)
        if self.fail_on is None:
            return 0
        workspace_id, label = self.fail_on
        if command.label == label and str(workspace_id) in command.argv:
            return 3
        return 0

    @property
    def labels(self) -> list[str]:
        """부른 단계 이름을 순서대로 돌려준다."""
        return [command.label for command in self.calls]


def _always_reused(workspace_id: int) -> str:
    return "reused"


def _drained(workspace_id: int) -> int:
    return 0


def test_build_step_commands_targets_the_given_workspace() -> None:
    """세 단계 모두 같은 workspace와 같은 어휘 버전을 겨냥한다."""
    commands = build_step_commands(workspace_id=910007, ontology_version="2")

    assert [command.label for command in commands] == ["추출", "해소", "판정"]
    assert [command.argv[2] for command in commands] == [
        EXTRACTION_MODULE,
        RESOLUTION_MODULE,
        ADJUDICATION_MODULE,
    ]
    for command in commands:
        assert command.argv[0] == sys.executable
        assert command.argv[1] == "-m"
        assert "--workspace-id" in command.argv
        assert command.argv[command.argv.index("--workspace-id") + 1] == "910007"
        assert "2" in command.argv

    # pending 확인은 추출 뒤에만 한다. 해소·판정은 이 큐를 비우지 않는다.
    assert [command.drains_observations for command in commands] == [
        True,
        False,
        False,
    ]


def test_run_pipeline_walks_every_workspace_in_order() -> None:
    """workspace마다 세 단계를 끝까지 밀고 다음으로 넘어간다."""
    runner = _Recorder()

    reports = run_pipeline(
        [910000, 910001],
        ontology_version="2",
        run_step=runner,
        copy_vocabulary=_always_reused,
        count_pending=_drained,
    )

    assert runner.labels == ["추출", "해소", "판정"] * 2
    assert [command.argv[4] for command in runner.calls] == [
        "910000",
        "910000",
        "910000",
        "910001",
        "910001",
        "910001",
    ]
    assert [report.workspace_id for report in reports] == [910000, 910001]
    assert all(len(report.steps) == 3 for report in reports)


def test_run_pipeline_ensures_vocabulary_before_the_first_step() -> None:
    """어휘를 먼저 보장한 뒤에 단계를 부른다."""
    events: list[str] = []
    runner = _Recorder()

    def _copy(workspace_id: int) -> str:
        events.append(f"vocab:{workspace_id}")
        return "copied"

    def _run(command: StepCommand) -> int:
        events.append(f"step:{command.label}")
        return runner(command)

    reports = run_pipeline(
        [910000],
        ontology_version="2",
        run_step=_run,
        copy_vocabulary=_copy,
        count_pending=_drained,
    )

    assert events[0] == "vocab:910000"
    assert reports[0].vocabulary == "copied"


def test_run_pipeline_stops_at_the_first_failing_step() -> None:
    """한 단계가 실패하면 남은 단계도 남은 workspace도 돌리지 않는다."""
    runner = _Recorder(fail_on=(910000, "해소"))

    with pytest.raises(SystemExit) as excinfo:
        run_pipeline(
            [910000, 910001],
            ontology_version="2",
            run_step=runner,
            copy_vocabulary=_always_reused,
            count_pending=_drained,
        )

    message = str(excinfo.value)
    assert "910000" in message
    assert "해소" in message
    assert "exit 3" in message
    assert runner.labels == ["추출", "해소"]


def test_run_pipeline_stops_when_observations_are_left_unprocessed() -> None:
    """추출이 exit 0이어도 큐가 남아 있으면 멈춘다."""
    runner = _Recorder()

    def _left_behind(workspace_id: int) -> int:
        return 4

    with pytest.raises(SystemExit) as excinfo:
        run_pipeline(
            [910000, 910001],
            ontology_version="2",
            run_step=runner,
            copy_vocabulary=_always_reused,
            count_pending=_left_behind,
        )

    message = str(excinfo.value)
    assert "910000" in message
    assert "4건" in message
    assert runner.labels == ["추출"]


class _FakeOntology:
    """workspace별 어휘 스냅샷만 흉내 내는 fake repository다.

    실제 repository처럼 같은 버전에 다른 내용을 넣으려 하면
    `OntologySnapshotConflict`를 던진다. 조용히 덮어쓰는 fake를 쓰면
    이 러너가 충돌을 어떻게 다루는지 드러나지 않는다.
    """

    def __init__(self) -> None:
        self.stored: dict[tuple[int, str], ExtractionVocabulary] = {}

    def get(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        version: str,
    ) -> ExtractionVocabulary | None:
        return self.stored.get((workspace_id, version))

    def ensure(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        vocabulary: ExtractionVocabulary,
    ) -> ExtractionVocabulary:
        key = (workspace_id, vocabulary.snapshot_id)
        found = self.stored.get(key)
        if found is not None:
            if found.predicates != vocabulary.predicates:
                raise OntologySnapshotConflict("다른 어휘다")
            return found
        self.stored[key] = vocabulary
        return vocabulary


class _FakeUow:
    """어휘 repository 하나만 들고 있는 fake unit of work다."""

    def __init__(self, ontology: _FakeOntology) -> None:
        self.ontology = ontology
        self.commits = 0

    def __enter__(self) -> _FakeUow:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1


def _vocabulary(version: str, predicate: str) -> ExtractionVocabulary:
    return ExtractionVocabulary(snapshot_id=version, predicates=(predicate,))


def test_copy_vocabulary_snapshot_copies_from_the_source() -> None:
    """원본의 어휘를 대상 workspace에 같은 버전으로 남긴다."""
    ontology = _FakeOntology()
    ontology.stored[(902, "2")] = _vocabulary("2", "works_at")

    result = copy_vocabulary_snapshot(
        lambda: _FakeUow(ontology),
        source_workspace_id=902,
        target_workspace_id=910000,
        ontology_version="2",
    )

    assert result == "copied"
    copied = ontology.stored[(910000, "2")]
    assert copied.predicates == ("works_at",)


def test_copy_vocabulary_snapshot_skips_an_existing_snapshot() -> None:
    """이미 있으면 그대로 두고 재사용이라고 알린다."""
    ontology = _FakeOntology()
    ontology.stored[(902, "2")] = _vocabulary("2", "works_at")
    ontology.stored[(910000, "2")] = _vocabulary("2", "works_at")

    result = copy_vocabulary_snapshot(
        lambda: _FakeUow(ontology),
        source_workspace_id=902,
        target_workspace_id=910000,
        ontology_version="2",
    )

    assert result == "reused"


def test_copy_vocabulary_snapshot_stops_without_a_source() -> None:
    """원본에 그 버전이 없으면 추출을 시작하지 않는다."""
    with pytest.raises(SystemExit) as excinfo:
        copy_vocabulary_snapshot(
            lambda: _FakeUow(_FakeOntology()),
            source_workspace_id=902,
            target_workspace_id=910000,
            ontology_version="2",
        )

    message = str(excinfo.value)
    assert "902" in message
    assert "publish_vocabulary_snapshot" in message


def test_copy_vocabulary_snapshot_reports_a_conflict() -> None:
    """같은 이름에 다른 어휘가 있으면 충돌을 삼키지 않는다.

    `get`으로 선확인하는 경로를 지나쳐도 막히는지 본다. 대상에 같은
    버전이 다른 내용으로 이미 있으면 `get`이 그것을 돌려주므로 정상
    경로에서는 재사용으로 끝난다. 그래서 여기서는 조회 키가 어긋나
    `ensure`까지 도달하는 경우를 만들어 확인한다.
    """
    ontology = _FakeOntology()
    ontology.stored[(902, "2")] = _vocabulary("2", "works_at")
    # 대상에는 버전 이름만 같고 내용이 다른 스냅샷이 이미 있다.
    ontology.stored[(910000, "2")] = _vocabulary("2", "lives_in")

    class _BlindOntology(_FakeOntology):
        """대상 조회만 못 보는 repository를 흉내 낸다."""

        def get(
            self,
            *,
            workspace_id: int,
            ontology_id: str,
            version: str,
        ) -> ExtractionVocabulary | None:
            if workspace_id == 910000:
                return None
            return ontology.get(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                version=version,
            )

    blind = _BlindOntology()
    blind.stored = ontology.stored

    with pytest.raises(SystemExit) as excinfo:
        copy_vocabulary_snapshot(
            lambda: _FakeUow(blind),
            source_workspace_id=902,
            target_workspace_id=910000,
            ontology_version="2",
        )

    message = str(excinfo.value)
    assert "910000" in message
    assert "--workspace-base" in message


def test_copy_vocabulary_snapshot_uses_the_extraction_contract_id() -> None:
    """추출 러너가 읽는 것과 같은 ontology_id로 남긴다."""
    seen: list[str] = []

    class _Watching(_FakeOntology):
        def get(
            self,
            *,
            workspace_id: int,
            ontology_id: str,
            version: str,
        ) -> ExtractionVocabulary | None:
            seen.append(ontology_id)
            return super().get(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                version=version,
            )

    ontology = _Watching()
    ontology.stored[(902, "2")] = _vocabulary("2", "works_at")

    copy_vocabulary_snapshot(
        lambda: _FakeUow(ontology),
        source_workspace_id=902,
        target_workspace_id=910000,
        ontology_version="2",
    )

    assert set(seen) == {CONTRACT_ID}
