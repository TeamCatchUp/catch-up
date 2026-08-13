"""정의가 생기기 전에 만들어진 entity_summary 문서를 지운다.

문서는 이제 채널에 걸린 정의가 만든다. 그 전에 만들어진 문서는
`kind='entity_summary' AND definition_id IS NULL`인 채로 남아 있는데,
이제 어떤 정의로도 다시 컴파일되지 않으므로 검토 큐와 문서 목록에서
낡은 카드로만 보인다. 이 러너는 그 옛 문서와 딸린 행을 한 번에 걷어낸다.

기본은 dry-run이다. 지울 대상을 표로만 세어 보여 주고, `--apply`를 준
실행에서만 실제로 지운다. 되돌릴 수 없는 일이라 실행 자체를 두 걸음으로
나눈 것이다.

사람이 승인·반려한 결정은 원래 지워지지 않는다. 결정과 그 근거는 나중에
왜 그렇게 정해졌는지 되짚는 기록이라, 기계가 다시 돌았다는 이유로 덮이거나
사라지면 안 된다. 이 러너는 그 규칙의 인정된 예외다 — 지우는 계기가 기계의
재실행이 아니라 사람이 `--apply`를 직접 붙여 실행하는 행위이기 때문이다.

지우는 순서는 FK를 거꾸로 거슬러 올라간다. 블록 판정 → 변경안의
`base_revision_id` 끊기 → 판 → 변경안 → 문서다. 변경안과 판은 서로를
가리키므로(`base_revision_id` ↔ `source_proposal_id`) 한쪽 참조를 먼저
NULL로 끊지 않으면 어느 쪽도 먼저 지워지지 않는다.

검색 projection은 여기서 건드리지 않는다. projection은 언제든 다시 만들 수
있는 사본이라 남은 조각은 재투영으로 정리된다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.cleanup_entity_summary_artifacts \
        --workspace-id 1
    uv run python -m catchup.evaluation.cleanup_entity_summary_artifacts \
        --workspace-id 1 --apply
"""

from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import ArtifactOwner
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeArtifactChangeProposal as ProposalRow
from catchup.db.models import KnowledgeArtifactRevision as RevisionRow
from catchup.db.models import KnowledgeBlockVerdict

LEGACY_KIND = "entity_summary"


@dataclass(frozen=True)
class CleanupCounts:
    """지웠거나 지울 행 수를 테이블별로 담는다."""

    artifacts: int
    revisions: int
    proposals: int
    block_verdicts: int
    artifact_owners: int

    @property
    def total(self) -> int:
        """모든 테이블을 합한 행 수다."""
        return (
            self.artifacts
            + self.revisions
            + self.proposals
            + self.block_verdicts
            + self.artifact_owners
        )


def _legacy_artifact_ids(
    session: Session,
    *,
    workspace_id: int,
) -> tuple[uuid.UUID, ...]:
    """정의 이전 entity_summary 문서의 식별자를 모은다.

    정의를 딛고 선 문서(`definition_id` 있음)는 지금도 컴파일 대상이므로
    범위 밖이다. 다른 kind와 다른 workspace도 마찬가지다.
    """
    rows = session.execute(
        select(KnowledgeArtifact.id)
        .where(KnowledgeArtifact.workspace_id == workspace_id)
        .where(KnowledgeArtifact.kind == LEGACY_KIND)
        .where(KnowledgeArtifact.definition_id.is_(None))
    ).scalars()
    return tuple(rows)


def _proposal_ids(
    session: Session,
    *,
    workspace_id: int,
    artifact_ids: tuple[uuid.UUID, ...],
) -> tuple[uuid.UUID, ...]:
    """지울 문서에 달린 변경안의 식별자를 모은다."""
    rows = session.execute(
        select(ProposalRow.id)
        .where(ProposalRow.workspace_id == workspace_id)
        .where(ProposalRow.artifact_id.in_(artifact_ids))
    ).scalars()
    return tuple(rows)


def _count(session: Session, statement: object) -> int:
    """세기 질의 하나를 돌려 수를 읽는다."""
    return session.execute(statement).scalar_one()


def _count_derived(
    session: Session,
    *,
    workspace_id: int,
    artifact_ids: tuple[uuid.UUID, ...],
    proposal_ids: tuple[uuid.UUID, ...],
) -> CleanupCounts:
    """문서와 딸린 행 수를 테이블별로 센다."""
    revisions = _count(
        session,
        select(func.count())
        .select_from(RevisionRow)
        .where(RevisionRow.workspace_id == workspace_id)
        .where(RevisionRow.artifact_id.in_(artifact_ids)),
    )
    verdicts = _count(
        session,
        select(func.count())
        .select_from(KnowledgeBlockVerdict)
        .where(KnowledgeBlockVerdict.workspace_id == workspace_id)
        .where(KnowledgeBlockVerdict.proposal_id.in_(proposal_ids)),
    )
    owners = _count(
        session,
        select(func.count())
        .select_from(ArtifactOwner)
        .where(ArtifactOwner.artifact_id.in_(artifact_ids)),
    )
    return CleanupCounts(
        artifacts=len(artifact_ids),
        revisions=revisions,
        proposals=len(proposal_ids),
        block_verdicts=verdicts,
        artifact_owners=owners,
    )


def _delete_all(
    session: Session,
    *,
    workspace_id: int,
    artifact_ids: tuple[uuid.UUID, ...],
    proposal_ids: tuple[uuid.UUID, ...],
) -> None:
    """FK를 거슬러 올라가는 순서로 지운다.

    판이 변경안을 가리키므로(`source_proposal_id`) 판을 먼저 지운다.
    변경안이 판을 가리키는 반대 방향은 그 전에 NULL로 끊는다.
    """
    session.execute(
        delete(KnowledgeBlockVerdict)
        .where(KnowledgeBlockVerdict.workspace_id == workspace_id)
        .where(KnowledgeBlockVerdict.proposal_id.in_(proposal_ids))
    )
    session.execute(
        update(ProposalRow)
        .where(ProposalRow.workspace_id == workspace_id)
        .where(ProposalRow.id.in_(proposal_ids))
        .values(base_revision_id=None)
    )
    session.execute(
        delete(RevisionRow)
        .where(RevisionRow.workspace_id == workspace_id)
        .where(RevisionRow.artifact_id.in_(artifact_ids))
    )
    session.execute(
        delete(ProposalRow)
        .where(ProposalRow.workspace_id == workspace_id)
        .where(ProposalRow.id.in_(proposal_ids))
    )
    # 담당자 행은 문서 삭제에 딸려 사라지지만(ondelete CASCADE) 여기서
    # 직접 지운다. 지우는 범위가 코드에 그대로 보여야 세어 준 수와 실제로
    # 사라진 행이 어긋나지 않는다.
    session.execute(
        delete(ArtifactOwner).where(
            ArtifactOwner.artifact_id.in_(artifact_ids)
        )
    )
    session.execute(
        delete(KnowledgeArtifact)
        .where(KnowledgeArtifact.workspace_id == workspace_id)
        .where(KnowledgeArtifact.id.in_(artifact_ids))
    )


def run_cleanup(
    session: Session,
    *,
    workspace_id: int,
    apply: bool,
) -> CleanupCounts:
    """정의 이전 entity_summary 문서를 세고, apply일 때만 지운다.

    돌려주는 수는 어느 쪽이든 "지울 대상"의 수다. dry-run에서는 지웠을 수,
    apply에서는 지운 수가 된다.
    """
    artifact_ids = _legacy_artifact_ids(session, workspace_id=workspace_id)
    if not artifact_ids:
        return CleanupCounts(0, 0, 0, 0, 0)

    proposal_ids = _proposal_ids(
        session,
        workspace_id=workspace_id,
        artifact_ids=artifact_ids,
    )
    counts = _count_derived(
        session,
        workspace_id=workspace_id,
        artifact_ids=artifact_ids,
        proposal_ids=proposal_ids,
    )
    if not apply:
        return counts

    _delete_all(
        session,
        workspace_id=workspace_id,
        artifact_ids=artifact_ids,
        proposal_ids=proposal_ids,
    )
    session.commit()
    return counts


def format_report(counts: CleanupCounts, *, apply: bool) -> str:
    """센 결과를 사람이 읽을 표로 적는다."""
    headline = "=== 삭제 결과 ===" if apply else "=== 삭제 대상 (dry-run) ==="
    lines = [
        headline,
        f"  knowledge_block_verdicts {counts.block_verdicts}",
        f"  knowledge_artifact_revisions {counts.revisions}",
        f"  knowledge_artifact_change_proposals {counts.proposals}",
        f"  artifact_owners {counts.artifact_owners}",
        f"  knowledge_artifacts {counts.artifacts}",
    ]
    if counts.total == 0:
        lines.append("  지울 옛 문서가 없다.")
    lines.append(
        "  검색 projection에 남은 조각은 여기서 지우지 않는다. 재투영으로 정리된다."
    )
    if not apply:
        lines.append("  실제로 지우려면 --apply를 붙여 다시 실행한다.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help=("정말로 지운다. 생략하면 지울 대상을 세어 보여 주기만 한다."),
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        counts = run_cleanup(
            session,
            workspace_id=args.workspace_id,
            apply=args.apply,
        )
    print(format_report(counts, apply=args.apply))
    engine.dispose()


if __name__ == "__main__":
    main()
