"""LongMemEval 검토 큐를 사람 없이 규칙으로 비운다.

벤치마크는 사람이 안건을 하나씩 판정해 줄 수 없다. 그래서 이 러너가
사람의 자리에 앉아 병합과 문서 변경안은 전부 승인하고, 모순은 "가장
최근 관찰이 참"이라는 규칙 하나로 판정한다.

판정은 사람과 똑같은 정문으로 들어간다 — `review_merge_proposal`,
`review_contradiction_proposal`, `review_artifact_proposal`이다. 상태를
SQL로 직접 바꾸면 결정 저널(누가 언제 정했나)이 비고, 그것을 지키는
DB CHECK를 우회하게 된다. 자동 판정도 감사 대상이라는 뜻에서 판정자
이름을 사람 이름과 구분되게 남긴다.

단계 순서는 `bench_adjudication.run_adjudication`이 고정한다. 병합
적용이 모순 감지보다 앞이라는 것이 핵심이다 — 뒤집으면 아직 하나로
묶이지 않은 후보의 주장이 비교 그룹에서 빠져 모순을 통째로 놓친다.

건별 실패는 그 자리에서 멈추지 않고 끝까지 시도한 뒤 모아서 보고한다.
한 건이라도 남으면 exit 1이다. 경고만 남기고 0으로 끝내면 오케스트레이터가
지식이 빠진 workspace를 완료로 기록한다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.longmemeval.run_bench_adjudication \\
        --workspace-id 902
"""

from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Callable

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.evaluation.longmemeval.bench_adjudication import REVIEWER_AUTO_ACCEPT
from catchup.evaluation.longmemeval.bench_adjudication import REVIEWER_RECENCY_RULE
from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationCounts
from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationSteps
from catchup.evaluation.longmemeval.bench_adjudication import StepOutcome
from catchup.evaluation.longmemeval.bench_adjudication import candidate_from_value
from catchup.evaluation.longmemeval.bench_adjudication import run_adjudication
from catchup.evaluation.longmemeval.bench_adjudication import select_winner
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpec
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpecError
from catchup.knowledge_maintenance.domain.artifact_definition import (
    serialize_selection_spec,
)
from catchup.knowledge_maintenance.domain.artifact_definition import (
    validate_selection_spec,
)
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_definition_artifacts,
)
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import (
    resolve_claim_conflicts,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    VERDICT_APPROVED as ARTIFACT_APPROVED,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    ProposalReviewError,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    review_artifact_proposal,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewError,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    review_contradiction_proposal,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    VERDICT_APPROVED as MERGE_APPROVED,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    MergeReviewError,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    review_merge_proposal,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

ONTOLOGY_VERSION = "2"
DEFAULT_WORKSPACE_ID = 902

DECISION_EVENT = "bench_adjudication_decided"
TIE_EXHAUSTED_EVENT = "bench_adjudication_tie_exhausted"

TEMPLATE_WORKSPACE_ID = 1
"""채널을 만든 사람을 베껴 올 기준 workspace를 나타낸다.

문항별 workspace는 러너가 찍어 내는 것이라 채널을 만들 사람이 없다.
`run_ingestion`이 company_id를 1번에서 베껴 오는 것과 같은 관례다.
"""

BENCH_SEED_NAMESPACE = uuid.UUID("2f3c9a2e-4d6b-4f31-9a37-6c1d0b5a7e42")
"""벤치 씨앗 행의 식별자를 유도할 이름공간을 나타낸다."""

BENCH_CHANNEL_NAME = "bench-llm-wiki"
BENCH_DEFINITION_KIND = "bench_entity_card"
BENCH_DEFINITION_PURPOSE = (
    "벤치마크가 만든 entity 하나를 카드 한 장으로 본다"
)

ENSURE_BENCH_CHANNEL_SQL = text(
    """
    INSERT INTO channels (id, workspace_id, name, created_by)
    VALUES (:channel_id, :workspace_id, :name, :created_by)
    ON CONFLICT DO NOTHING
    """
)

ENSURE_BENCH_DEFINITION_SQL = text(
    """
    INSERT INTO artifact_definitions (
        id, workspace_id, channel_id, kind, purpose,
        selection_spec, created_by
    )
    VALUES (
        :definition_id, :workspace_id, :channel_id, :kind, :purpose,
        CAST(:selection_spec AS jsonb), :created_by
    )
    ON CONFLICT ON CONSTRAINT uq_artifact_definitions_channel_kind
    DO UPDATE SET selection_spec = EXCLUDED.selection_spec
    """
)

BENCH_AUTHOR_SQL = text(
    """
    SELECT user_id
    FROM user_workspaces
    WHERE workspace_id = :template_workspace_id
    ORDER BY user_id
    LIMIT 1
    """
)

FALLBACK_AUTHOR_SQL = text("SELECT min(id) FROM users")

BENCH_CHANNEL_ID_SQL = text(
    """
    SELECT id
    FROM channels
    WHERE workspace_id = :workspace_id AND name = :name
    """
)


class BenchDefinitionError(RuntimeError):
    """벤치 workspace에 카드 정의를 마련하지 못했음을 나타낸다."""


def bench_channel_id(workspace_id: int) -> uuid.UUID:
    """문항 workspace의 벤치 채널 식별자를 번호에서 만든다.

    실행마다 새 uuid를 뽑으면 두 번째 실행이 채널 이름 UNIQUE에 걸려
    깨진다. 번호에서 유도하면 몇 번을 돌려도 같은 행을 가리킨다.
    """
    return uuid.uuid5(BENCH_SEED_NAMESPACE, f"channel:{workspace_id}")


def bench_definition_id(workspace_id: int) -> uuid.UUID:
    """문항 workspace의 벤치 정의 식별자를 번호에서 만든다."""
    return uuid.uuid5(BENCH_SEED_NAMESPACE, f"definition:{workspace_id}")


def bench_selection_spec(vocabulary: ExtractionVocabulary) -> SelectionSpec:
    """어휘의 entity 종류를 하나도 빠뜨리지 않는 선택 규칙을 만든다.

    종류를 골라 넣으면 고르지 않은 종류의 카드가 조용히 사라지고,
    벤치마크는 그만큼 지식이 빠진 채로 점수를 낸다. 관계 경로는 두지
    않고 절도 고르지 않는다 — 절을 고르지 않음(None)은 어휘의 모든
    절을 싣는다는 뜻이라, 이 한 벌이 정의 없이 전부 싣던 예전 컴파일러와
    같은 범위가 된다.
    """
    return SelectionSpec(
        entity_types=tuple(
            entry.name for entry in vocabulary.entity_type_entries
        ),
        relation_paths=(),
        predicate_sections=None,
    )


def _bench_author_id(session: Session) -> int:
    """씨앗 행의 작성자로 쓸 사용자를 고른다.

    Raises:
        BenchDefinitionError: 쓸 수 있는 사용자가 하나도 없을 때 던진다.
            채널의 created_by는 NOT NULL FK라 사람 없이는 행이 서지
            않는다.
    """
    found = session.execute(
        BENCH_AUTHOR_SQL,
        {"template_workspace_id": TEMPLATE_WORKSPACE_ID},
    ).scalar()
    if found is None:
        found = session.execute(FALLBACK_AUTHOR_SQL).scalar()
    if found is None:
        raise BenchDefinitionError(
            "채널을 만들 사용자가 DB에 하나도 없다. 벤치 workspace에 카드"
            " 정의를 넣으려면 users 행이 최소 하나 필요하다."
        )
    return int(found)


def ensure_bench_definition(
    session_factory: Callable[[], Session],
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
) -> None:
    """문항 workspace에 벤치용 채널과 카드 정의를 마련한다.

    무엇을 문서로 만들지는 정의가 정하는데, 문항별 workspace는 러너가
    찍어 내는 것이라 정의를 넣어 줄 사람이 없다. 정의가 없으면 컴파일
    단계가 매번 실패로 끝나고 회차 전체가 실패로 기록된다.

    정의는 채널 아래에 놓이므로 채널을 먼저 세운다. 둘 다 식별자를
    workspace 번호에서 유도하고 충돌을 흘려보내므로 몇 번을 돌려도
    행은 한 벌뿐이다. 정의의 선택 규칙만은 덮어쓴다 — 어휘에 종류가
    늘면 카드 범위도 함께 늘어야 한다.

    선택 규칙은 넣기 전에 어휘로 검사한다. 컴파일러는 어긋난 정의를
    건너뛰기만 하므로, 여기서 막지 않으면 정의가 있는데도 카드가 한
    장도 나오지 않는 자리가 생긴다.

    Raises:
        BenchDefinitionError: 어휘에 entity 종류가 없거나, 선택 규칙이
            어휘와 어긋나거나, 작성자로 쓸 사용자가 없을 때 던진다.
    """
    spec = bench_selection_spec(vocabulary)
    if not spec.entity_types:
        raise BenchDefinitionError(
            f"어휘 스냅샷에 entity 종류가 없다. workspace {workspace_id}의"
            " 어휘를 먼저 발행한다."
        )
    try:
        validate_selection_spec(spec, vocabulary)
    except SelectionSpecError as error:
        raise BenchDefinitionError(
            f"벤치 카드 정의가 어휘와 어긋난다: {error}"
        ) from error

    definition_id = bench_definition_id(workspace_id)
    with session_factory() as session:
        created_by = _bench_author_id(session)
        session.execute(
            ENSURE_BENCH_CHANNEL_SQL,
            {
                "channel_id": bench_channel_id(workspace_id),
                "workspace_id": workspace_id,
                "name": BENCH_CHANNEL_NAME,
                "created_by": created_by,
            },
        )
        # 이름이 같은 채널이 이미 다른 식별자로 있으면 위 INSERT는
        # 조용히 흘러간다. 유도한 식별자를 그대로 쓰면 정의가 없는
        # 채널을 가리키므로, 실제로 선 행을 다시 읽어 쓴다.
        channel_id = session.execute(
            BENCH_CHANNEL_ID_SQL,
            {"workspace_id": workspace_id, "name": BENCH_CHANNEL_NAME},
        ).scalar_one()
        session.execute(
            ENSURE_BENCH_DEFINITION_SQL,
            {
                "definition_id": definition_id,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "kind": BENCH_DEFINITION_KIND,
                "purpose": BENCH_DEFINITION_PURPOSE,
                "selection_spec": json.dumps(
                    serialize_selection_spec(spec), ensure_ascii=False
                ),
                "created_by": created_by,
            },
        )
        session.commit()

    logger.info(
        "bench_adjudication_definition_seeded",
        workspace_id=workspace_id,
        channel_id=str(channel_id),
        kind=BENCH_DEFINITION_KIND,
        entity_types=list(spec.entity_types),
    )


def _load_vocabulary(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    version: str,
) -> ExtractionVocabulary | None:
    """모순 비교와 카드 컴파일이 쓸 어휘 스냅샷을 읽는다."""
    with uow:
        return uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=CONTRACT_ID,
            version=version,
        )


def _approve_merges(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
) -> StepOutcome:
    """계류 중인 병합 안건을 전부 승인한다.

    벤치마크에서 병합 안건은 judge가 이미 같은 대상이라고 판정한
    것뿐이다. 사람의 자리는 그 판정을 확정하는 일이므로 전부 승인한다.

    실패한 안건은 세어 돌려준다. 경고만 남기고 0으로 끝내면 병합되지
    않은 후보가 남은 workspace가 완료로 기록된다.
    """
    with uow:
        pending = uow.mutation_proposals.list_pending_duplicates(
            workspace_id=workspace_id,
        )

    approved = 0
    failed = 0
    for proposal in pending:
        try:
            review_merge_proposal(
                uow,
                workspace_id=workspace_id,
                proposal_id=proposal.id,
                verdict=MERGE_APPROVED,
                reviewer=REVIEWER_AUTO_ACCEPT,
            )
        except MergeReviewError as error:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="merge",
                reason=str(error),
            )
            failed += 1
            continue
        approved += 1
        logger.info(
            DECISION_EVENT,
            proposal_id=str(proposal.id),
            kind="merge",
            winner=None,
            tie_break_used=False,
            reviewer=REVIEWER_AUTO_ACCEPT,
        )
    return StepOutcome(done=approved, failed=failed)


def _apply_mutations(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    *,
    workspace_id: int,
) -> StepOutcome:
    """결정 저널을 적용한다. 승인·판정이 만든 명령만 소비한다."""
    result = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)
    if result.proposals_failed:
        logger.warning(
            "bench_adjudication_apply_failed",
            failed=result.proposals_failed,
        )
    return StepOutcome(
        done=result.proposals_applied,
        failed=result.proposals_failed,
    )


def _detect_conflicts(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
) -> StepOutcome:
    """값이 어긋나는 주장 쌍을 찾아 안건으로 남긴다."""
    result = resolve_claim_conflicts(
        workspace_id=workspace_id,
        vocabulary=vocabulary,
        uow=uow,
    )
    return StepOutcome(done=result.conflicts_found)


def _adjudicate_contradictions(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
) -> StepOutcome:
    """계류 중인 모순 안건을 recency 규칙으로 판정한다.

    판정하지 못한 안건은 세어 돌려준다. 그 안건이 계류로 남으면 진 값이
    살아 있는 채로 카드가 컴파일된다.
    """
    with uow:
        pending = uow.mutation_proposals.list_pending_contradictions(
            workspace_id=workspace_id,
        )

    decided = 0
    failed = 0
    for proposal in pending:
        candidates = [candidate_from_value(v) for v in proposal.values]
        if not candidates:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="contradiction",
                reason="값 후보가 없다",
            )
            failed += 1
            continue
        selection = select_winner(candidates)
        if selection.tie_exhausted:
            # 입력 유래 키를 끝까지 써도 갈리지 않은 후보가 남았다는
            # 뜻이다. 승자 값과 닫히는 구간이 같아 판정은 유효하지만,
            # 재실행 시 어느 claim_id가 뽑히는지는 입력 순서를 탄다.
            logger.warning(
                TIE_EXHAUSTED_EVENT,
                proposal_id=str(proposal.id),
                kind="contradiction",
                winner=str(selection.claim_id),
            )
        try:
            review_contradiction_proposal(
                uow,
                workspace_id=workspace_id,
                proposal_id=proposal.id,
                winner_claim_id=selection.claim_id,
                reviewer=REVIEWER_RECENCY_RULE,
            )
        except ContradictionReviewError as error:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="contradiction",
                reason=str(error),
            )
            failed += 1
            continue
        decided += 1
        logger.info(
            DECISION_EVENT,
            proposal_id=str(proposal.id),
            kind="contradiction",
            winner=str(selection.claim_id),
            tie_break_used=selection.tie_break_used,
            reviewer=REVIEWER_RECENCY_RULE,
        )
    return StepOutcome(done=decided, failed=failed)


def _compile_artifacts(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
) -> StepOutcome:
    """정의가 고른 문서를 컴파일해 변경안으로 올린다.

    멱등 키가 이미 결정된 변경안과 부딪힌 노드는 컴파일러가 건너뛰고
    충돌로 센다. 그 entity의 새 카드는 만들어지지 않으므로 실패로 올려
    보낸다 — 로그에만 남기면 exit 0으로 끝나 오케스트레이터가 카드 빠진
    workspace를 완료로 기록한다.

    읽은 정의가 하나도 없으면 그 자체를 실패 한 건으로 센다. 무엇을
    문서로 만들지는 정의가 정하므로, 정의가 없는 workspace는 카드가
    한 장도 없이 조용히 통과해 답이 빈 채로 채점된다. 벤치 정의는
    `ensure_bench_definition`이 회차 시작 전에 마련하므로, 여기 걸린다면
    씨앗 넣기가 건너뛰어졌다는 뜻이다.
    """
    result = compile_definition_artifacts(
        uow,
        workspace_id=workspace_id,
        vocabulary=vocabulary,
    )
    logger.info(
        "bench_adjudication_compiled",
        definitions_considered=result.definitions_considered,
        nodes_considered=result.nodes_considered,
        created=result.proposals_created,
        revived=result.proposals_revived,
        unchanged=result.unchanged_skipped,
        conflicted=result.proposals_conflicted,
        blocks_suppressed=result.blocks_suppressed,
    )
    if result.definitions_considered == 0:
        logger.warning(
            "bench_adjudication_no_definitions",
            workspace_id=workspace_id,
        )
        return StepOutcome(done=0, failed=1)
    return StepOutcome(
        done=result.proposals_created + result.proposals_revived,
        failed=result.proposals_conflicted,
    )


def _approve_artifacts(uow: KnowledgeMaintenanceUnitOfWork) -> StepOutcome:
    """계류 중인 문서 변경안을 전부 승인해 판으로 확정한다.

    실패한 변경안은 세어 돌려준다. 승인되지 않은 카드는 조회에 잡히지
    않으므로 그만큼 답이 비어 나온다.
    """
    with uow:
        pending = uow.artifacts.list_pending_proposals()

    approved = 0
    failed = 0
    for proposal in pending:
        try:
            review_artifact_proposal(
                uow,
                proposal_id=proposal.id,
                verdict=ARTIFACT_APPROVED,
                reviewer=REVIEWER_AUTO_ACCEPT,
            )
        except ProposalReviewError as error:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="artifact",
                reason=str(error),
            )
            failed += 1
            continue
        approved += 1
        logger.info(
            DECISION_EVENT,
            proposal_id=str(proposal.id),
            kind="artifact",
            winner=None,
            tie_break_used=False,
            reviewer=REVIEWER_AUTO_ACCEPT,
        )
    return StepOutcome(done=approved, failed=failed)


def report_counts(counts: AdjudicationCounts) -> int:
    """한 회차 결과를 찍고 종료 코드를 정한다.

    처리하지 못한 안건이 하나라도 있으면 1이다. 건별 실패를 경고로만
    남기고 0으로 끝내면 오케스트레이터는 exit code만 보므로 지식이 빠진
    workspace를 완료로 기록하고 다음 문항으로 넘어간다.
    """
    print("=== 무인 판정 결과 ===")
    print(f"  ① 병합 자동 승인 {counts.merges_approved}")
    print(f"  ② 병합 적용 {counts.merges_applied}")
    print(f"  ③ 모순 감지 {counts.conflicts_found}")
    print(f"  ④ 모순 판정(recency) {counts.contradictions_decided}")
    print(f"  ⑤ 판정 적용 {counts.supersedes_applied}")
    print(f"  ⑥ 카드 컴파일 {counts.artifacts_compiled}")
    print(f"  ⑦ 카드 자동 승인 {counts.artifacts_approved}")
    if not counts.failures:
        return 0

    # 여기까지 왔다는 것은 전 건을 시도했다는 뜻이다. 첫 실패에서 멈추지
    # 않는 대신, 남은 안건이 있으면 실패로 끝낸다.
    print("=== 처리하지 못한 안건 ===")
    print(f"  병합 승인 실패 {counts.merges_failed}")
    print(f"  적용 실패 {counts.mutations_failed}")
    print(f"  모순 판정 실패 {counts.contradictions_failed}")
    print(f"  카드 컴파일 충돌 {counts.compilations_failed}")
    print(f"  카드 승인 실패 {counts.artifacts_failed}")
    print(
        f"  합계 {counts.failures}건이 계류로 남았다. "
        "그만큼 지식이 빠진 채로 점수가 나오므로 실패로 끝낸다. "
        "bench_adjudication_skipped·bench_adjudication_apply_failed 로그에서 "
        "사유를 확인한다."
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-id",
        type=int,
        default=DEFAULT_WORKSPACE_ID,
    )
    parser.add_argument(
        "--ontology-version",
        default=ONTOLOGY_VERSION,
        help="모순 비교와 카드에 쓸 어휘 스냅샷 버전을 정한다.",
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory,
        workspace_id=args.workspace_id,
    )

    def uow_factory() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            session_factory,
            workspace_id=args.workspace_id,
        )

    try:
        vocabulary = _load_vocabulary(
            uow,
            workspace_id=args.workspace_id,
            version=args.ontology_version,
        )
        if vocabulary is None:
            print(
                f"어휘 스냅샷 v{args.ontology_version}이 없다. "
                f"publish_vocabulary_snapshot을 먼저 돌린다."
            )
            return 1
        if not vocabulary.predicate_entries:
            # 사전에 치역이 없으면 비교 대상이 하나도 남지 않아 모순이
            # 0건으로 떨어진다. 조용히 통과하면 "모순이 없다"로 읽힌다.
            print(
                f"어휘 스냅샷 v{args.ontology_version}에 predicate 사전 "
                f"항목이 없다. 치역을 담은 사전을 먼저 발행한다."
            )
            return 1

        # 카드 정의는 판정보다 먼저 서 있어야 한다. 컴파일 단계에 와서야
        # 없다는 것을 알면 그 회차는 이미 실패로 끝난다.
        try:
            ensure_bench_definition(
                session_factory,
                workspace_id=args.workspace_id,
                vocabulary=vocabulary,
            )
        except BenchDefinitionError as error:
            print(str(error))
            return 1

        steps = AdjudicationSteps(
            approve_merges=lambda: _approve_merges(
                uow, workspace_id=args.workspace_id
            ),
            apply_mutations=lambda: _apply_mutations(
                uow_factory, workspace_id=args.workspace_id
            ),
            detect_conflicts=lambda: _detect_conflicts(
                uow,
                workspace_id=args.workspace_id,
                vocabulary=vocabulary,
            ),
            adjudicate_contradictions=lambda: _adjudicate_contradictions(
                uow, workspace_id=args.workspace_id
            ),
            compile_artifacts=lambda: _compile_artifacts(
                uow,
                workspace_id=args.workspace_id,
                vocabulary=vocabulary,
            ),
            approve_artifacts=lambda: _approve_artifacts(uow),
        )

        counts = run_adjudication(steps)
    finally:
        engine.dispose()

    return report_counts(counts)


if __name__ == "__main__":
    raise SystemExit(main())
