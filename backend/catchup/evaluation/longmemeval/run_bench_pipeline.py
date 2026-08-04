"""manifest에 적힌 bench workspace 전부에 지식 파이프라인을 돌린다.

수집 러너는 문항마다 workspace를 따로 만든다. 그런데 그다음 단계인 추출·
해소·판정 러너는 전부 `--workspace-id` 하나만 받고 기본값도 옛 단일
workspace다. 그래서 수집만 격리해 두면 나머지 workspace 39개는 아무도
처리하지 않는데, QA·채점은 manifest를 읽어 40개를 모두 정상 격리 실행처럼
조회한다 — 대부분 빈 지식 위에서 점수가 나온다. 이 러너가 그 사이를 잇는다.

workspace 하나에 대해 네 가지를 순서대로 한다.

1. 어휘 스냅샷 보장: 스냅샷 원본 workspace(`--source-workspace-id`)의
   어휘를 읽어 이 workspace에도 같은 버전으로 남긴다. 이것이 없으면
   판정 러너가 "어휘 스냅샷이 없다"로 끝난다.
2. 추출: `run_extraction_pipeline`
3. 해소: `run_resolution_pipeline`
4. 무인 판정: `run_bench_adjudication`

2~4는 기존 CLI 러너를 subprocess로 부른다. 같은 일을 여기서 다시 구현하면
러너와 이 러너가 조용히 갈라지고, 어느 쪽이 벤치의 정본인지 알 수 없게
된다. 한 단계라도 exit code가 0이 아니면 그 자리에서 멈춘다 — 실패한
workspace를 건너뛰고 이어 가면 빈 지식이 섞인 채로 점수가 나온다.

어휘 발행만 subprocess가 아니라 in-process다. 원본 workspace의 어휘를
읽어 그대로 옮기는 일이라 파일 입력을 받는 발행 러너의 계약과 맞지 않고,
`uow.ontology.ensure`가 이미 "있으면 그대로, 다르면 충돌"을 보장한다.

추출이 끝나면 그 workspace의 pending `observation.ready` 이벤트가 0인지
확인한다. 러너는 실패한 건을 재시도 대기로 되돌리고 exit 0으로 끝날 수
있어서, 종료 코드만으로는 "다 처리했다"를 말할 수 없다.

실행:
    uv run python -m catchup.evaluation.longmemeval.run_bench_pipeline \\
        --manifest experiments/longmemeval/results/workspace_manifest.json \\
        --ontology-version 2
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.evaluation.longmemeval.workspace_manifest import DEFAULT_MANIFEST_PATH
from catchup.evaluation.longmemeval.workspace_manifest import load_manifest
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventStatus
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType
from catchup.knowledge_maintenance.ports.ontology import OntologySnapshotConflict

__all__ = [
    "DEFAULT_SOURCE_WORKSPACE_ID",
    "EXTRACTION_MODULE",
    "RESOLUTION_MODULE",
    "ADJUDICATION_MODULE",
    "StepCommand",
    "StepReport",
    "WorkspaceReport",
    "build_step_commands",
    "copy_vocabulary_snapshot",
    "count_pending_observation_events",
    "run_pipeline",
    "subprocess_step_runner",
]

DEFAULT_SOURCE_WORKSPACE_ID = 902
"""어휘 스냅샷을 베껴 올 원본 workspace를 나타낸다.

문항별 workspace는 러너가 찍어 내는 것이라 사람이 사전을 발행해 둔 적이
없다. 기존 평가 workspace에 발행된 사전을 원본으로 삼는다.
"""

EXTRACTION_MODULE = "catchup.evaluation.run_extraction_pipeline"
RESOLUTION_MODULE = "catchup.evaluation.run_resolution_pipeline"
ADJUDICATION_MODULE = "catchup.evaluation.longmemeval.run_bench_adjudication"

UNFINISHED_EVENT_STATUSES = [
    PipelineEventStatus.PENDING.value,
    PipelineEventStatus.PROCESSING.value,
]
"""아직 소화되지 않은 큐 상태를 나타낸다.

`processing`도 센다. 러너가 집어 갔다가 끝내지 못한 것도 처리되지 않은
일이고, 빼고 세면 "다 끝났다"가 거짓이 된다.
"""

PENDING_OBSERVATION_EVENTS_SQL = text(
    """
    SELECT count(*)
    FROM knowledge_pipeline_outbox
    WHERE workspace_id = :workspace_id
      AND event_type = :event_type
      AND status = ANY(:statuses)
    """
)
"""추출이 아직 소화하지 못한 일의 수를 센다."""


@dataclass(frozen=True, slots=True)
class StepCommand:
    """한 workspace에 돌릴 단계 하나를 담는다.

    Attributes:
        label: 사람이 읽을 단계 이름을 나타낸다.
        argv: subprocess에 넘길 인자를 담는다.
        drains_observations: 이 단계 뒤에 pending 이벤트 0을 확인할지
            나타낸다. 추출만 해당한다.
    """

    label: str
    argv: tuple[str, ...]
    drains_observations: bool = False


@dataclass(frozen=True, slots=True)
class StepReport:
    """단계 하나의 실행 결과를 담는다."""

    label: str
    seconds: float


@dataclass(frozen=True, slots=True)
class WorkspaceReport:
    """workspace 하나의 실행 결과를 담는다.

    Attributes:
        workspace_id: 처리한 workspace를 나타낸다.
        vocabulary: 어휘를 새로 남겼는지(`copied`) 이미 있었는지(`reused`)
            나타낸다.
        steps: 단계별 소요 시간을 순서대로 담는다.
    """

    workspace_id: int
    vocabulary: str
    steps: tuple[StepReport, ...]

    @property
    def seconds(self) -> float:
        """이 workspace에 걸린 전체 시간을 나타낸다."""
        return sum(step.seconds for step in self.steps)


StepRunner = Callable[[StepCommand], int]
"""단계 하나를 돌리고 exit code를 돌려주는 함수의 모양을 정의한다."""

VocabularyCopier = Callable[[int], str]
"""workspace 하나에 어휘를 보장하고 `copied`/`reused`를 돌려준다."""

PendingCounter = Callable[[int], int]
"""workspace 하나의 미처리 observation 이벤트 수를 돌려준다."""


def build_step_commands(
    *,
    workspace_id: int,
    ontology_version: str,
) -> tuple[StepCommand, ...]:
    """workspace 하나에 돌릴 세 단계를 순서대로 만든다.

    모듈 실행(`-m`)으로 부른다. 러너들이 패키지 안의 상대 import를 쓰므로
    파일 경로로 부르면 import가 깨진다. 해석기는 `sys.executable`이다 —
    벤치가 도는 가상환경 밖의 파이썬이 잡히면 의존성이 달라진다.
    """
    workspace = str(workspace_id)
    return (
        StepCommand(
            label="추출",
            argv=(
                sys.executable,
                "-m",
                EXTRACTION_MODULE,
                "--workspace-id",
                workspace,
                "--ontology-version",
                ontology_version,
            ),
            drains_observations=True,
        ),
        StepCommand(
            label="해소",
            argv=(
                sys.executable,
                "-m",
                RESOLUTION_MODULE,
                "--workspace-id",
                workspace,
                "--vocabulary-version",
                ontology_version,
            ),
        ),
        StepCommand(
            label="판정",
            argv=(
                sys.executable,
                "-m",
                ADJUDICATION_MODULE,
                "--workspace-id",
                workspace,
                "--ontology-version",
                ontology_version,
            ),
        ),
    )


def subprocess_step_runner(command: StepCommand) -> int:
    """단계를 자식 프로세스로 돌리고 exit code를 돌려준다.

    출력은 가로채지 않는다. 러너들이 진행 상황을 stdout에 흘려 쓰는데,
    모아 두었다가 끝에 뱉으면 몇 시간짜리 실행이 멈춘 것처럼 보인다.
    """
    return subprocess.run(command.argv, check=False).returncode


def copy_vocabulary_snapshot(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    *,
    source_workspace_id: int,
    target_workspace_id: int,
    ontology_version: str,
) -> str:
    """원본 workspace의 어휘를 이 workspace에도 같은 버전으로 남긴다.

    `ensure`를 바로 부르지 않고 `get`으로 먼저 확인한다. 이미 있는 것이
    정상 재실행인데, `ensure`는 내용이 다르면 `OntologySnapshotConflict`를
    던지므로 그 경우를 "이미 있음"과 구별해 다뤄야 한다. 충돌은 삼키지
    않는다 — 같은 버전 이름이 workspace마다 다른 사전을 가리키면 어느
    사전으로 뽑은 후보인지 기록이 거짓이 된다.

    Returns:
        새로 남겼으면 "copied", 이미 있었으면 "reused"를 돌려준다.

    Raises:
        SystemExit: 원본에 그 버전이 없거나, 대상에 같은 이름의 다른
            어휘가 이미 있을 때 낸다.
    """
    with uow_factory() as uow:
        existing = uow.ontology.get(
            workspace_id=target_workspace_id,
            ontology_id=CONTRACT_ID,
            version=ontology_version,
        )
    if existing is not None:
        return "reused"

    with uow_factory() as uow:
        source = uow.ontology.get(
            workspace_id=source_workspace_id,
            ontology_id=CONTRACT_ID,
            version=ontology_version,
        )
    if source is None:
        raise SystemExit(
            f"원본 workspace {source_workspace_id}에 어휘 스냅샷 "
            f"{CONTRACT_ID} v{ontology_version}이 없다. "
            "publish_vocabulary_snapshot으로 먼저 발행하거나 "
            "`--source-workspace-id`를 사전이 있는 workspace로 바꾼다."
        )

    with uow_factory() as uow:
        try:
            uow.ontology.ensure(
                workspace_id=target_workspace_id,
                ontology_id=CONTRACT_ID,
                vocabulary=source,
            )
        except OntologySnapshotConflict as error:
            raise SystemExit(
                f"workspace {target_workspace_id}에 이미 v{ontology_version} "
                f"이름으로 다른 어휘가 있다: {error}. 이 번호를 다른 실행이 "
                "쓰고 있다는 뜻이므로 `--workspace-base`를 옮겨 다시 수집한다."
            ) from error
        uow.commit()
    return "copied"


def count_pending_observation_events(
    session: Session,
    *,
    workspace_id: int,
) -> int:
    """추출이 아직 소화하지 못한 일의 수를 센다.

    읽기만 한다. 평가 러너가 큐 상태를 건드리면 같은 실행을 두 번 돌린
    결과가 달라진다.
    """
    return (
        session.execute(
            PENDING_OBSERVATION_EVENTS_SQL,
            {
                "workspace_id": workspace_id,
                "event_type": PipelineEventType.OBSERVATION_READY.value,
                "statuses": UNFINISHED_EVENT_STATUSES,
            },
        ).scalar()
        or 0
    )


def run_pipeline(
    workspace_ids: Sequence[int],
    *,
    ontology_version: str,
    run_step: StepRunner,
    copy_vocabulary: VocabularyCopier,
    count_pending: PendingCounter,
) -> tuple[WorkspaceReport, ...]:
    """workspace를 하나씩 끝까지 밀고, 실패하면 그 자리에서 멈춘다.

    workspace 단위로 완주시키고 다음으로 넘어간다. 단계별로 전체
    workspace를 훑으면 중간에 멈췄을 때 어디까지 갔는지가 workspace마다
    달라져 되짚기 어렵다.

    Raises:
        SystemExit: 단계가 0이 아닌 코드로 끝났거나, 추출 뒤에도 처리하지
            못한 observation 이벤트가 남았을 때 낸다.
    """
    reports: list[WorkspaceReport] = []
    for index, workspace_id in enumerate(workspace_ids, start=1):
        print(
            f"\n=== workspace {workspace_id} "
            f"({index}/{len(workspace_ids)}) ==="
        )
        vocabulary = copy_vocabulary(workspace_id)
        print(f"  어휘 v{ontology_version}: {vocabulary}")

        steps: list[StepReport] = []
        for command in build_step_commands(
            workspace_id=workspace_id,
            ontology_version=ontology_version,
        ):
            started = time.monotonic()
            code = run_step(command)
            elapsed = time.monotonic() - started
            if code != 0:
                raise SystemExit(
                    f"workspace {workspace_id}의 {command.label} 단계가 "
                    f"exit {code}로 끝났다: {' '.join(command.argv)}. "
                    "남은 workspace는 돌리지 않는다 — 실패한 workspace를 "
                    "건너뛰면 빈 지식이 섞인 채로 점수가 나온다."
                )
            if command.drains_observations:
                remaining = count_pending(workspace_id)
                if remaining:
                    raise SystemExit(
                        f"workspace {workspace_id}의 {command.label}가 끝난 "
                        f"뒤에도 처리하지 못한 observation 이벤트가 "
                        f"{remaining}건 남았다. 추출 러너는 실패한 건을 "
                        "재시도 대기로 되돌리고 정상 종료하므로 exit code만 "
                        "믿을 수 없다. 로그에서 실패 원인을 확인한다."
                    )
            steps.append(StepReport(label=command.label, seconds=elapsed))
            print(f"  {command.label}: {elapsed:.1f}s")

        reports.append(
            WorkspaceReport(
                workspace_id=workspace_id,
                vocabulary=vocabulary,
                steps=tuple(steps),
            )
        )
    return tuple(reports)


def print_summary(reports: Sequence[WorkspaceReport]) -> None:
    """workspace 수와 단계별 누적 시간을 한 번에 보여 준다."""
    print("\n=== 벤치 파이프라인 결과 ===")
    print(f"  workspace: {len(reports)}")
    copied = sum(1 for report in reports if report.vocabulary == "copied")
    print(f"  어휘 발행: 신규 {copied} · 재사용 {len(reports) - copied}")
    totals: dict[str, float] = {}
    for report in reports:
        for step in report.steps:
            totals[step.label] = totals.get(step.label, 0.0) + step.seconds
    for label, seconds in totals.items():
        print(f"  {label} 누적: {seconds:.1f}s")
    print(f"  전체: {sum(report.seconds for report in reports):.1f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="수집 러너가 쓴 문항-workspace 대응표를 정한다.",
    )
    parser.add_argument(
        "--ontology-version",
        required=True,
        help="세 단계가 함께 쓸 어휘 스냅샷 버전을 정한다.",
    )
    parser.add_argument(
        "--source-workspace-id",
        type=int,
        default=DEFAULT_SOURCE_WORKSPACE_ID,
        help="어휘 스냅샷을 베껴 올 원본 workspace를 정한다.",
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        raise SystemExit(
            f"manifest가 없다: {args.manifest}. 수집 러너를 먼저 돌린다. "
            "수집이 중간에 깨졌다면 최종 manifest는 만들어지지 않는다."
        )

    assignments = load_manifest(args.manifest)
    workspace_ids = sorted(
        {assignment.workspace_id for assignment in assignments}
    )
    if not workspace_ids:
        raise SystemExit(f"manifest에 workspace가 없다: {args.manifest}")

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _copy(workspace_id: int) -> str:
        return copy_vocabulary_snapshot(
            lambda: KnowledgeMaintenanceUnitOfWork(session_factory),
            source_workspace_id=args.source_workspace_id,
            target_workspace_id=workspace_id,
            ontology_version=args.ontology_version,
        )

    def _count(workspace_id: int) -> int:
        with session_factory() as session:
            return count_pending_observation_events(
                session,
                workspace_id=workspace_id,
            )

    print(
        f"workspace {len(workspace_ids)}개 "
        f"({workspace_ids[0]}~{workspace_ids[-1]}), "
        f"어휘 v{args.ontology_version}, "
        f"원본 workspace {args.source_workspace_id}"
    )
    try:
        reports = run_pipeline(
            workspace_ids,
            ontology_version=args.ontology_version,
            run_step=subprocess_step_runner,
            copy_vocabulary=_copy,
            count_pending=_count,
        )
    finally:
        engine.dispose()

    print_summary(reports)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
