"""canonical entity의 요약 카드를 결정론으로 컴파일한다.

LLM을 부르지 않는다. 카드는 이미 저장된 claim과 계류 중인 안건을 정해진
순서로 늘어놓은 것뿐이고, 같은 입력이면 같은 본문이 나와야 한다. 본문이
실행마다 흔들리면 내용 지문이 매번 달라져 사람이 이미 본 카드가 검토
큐에 다시 쌓인다.

값을 고르지 않는다. 한 predicate에 값이 여럿이면 전부 나열하고, 어느
값이 맞는지 묻는 일은 열린 질문 블록이 맡는다. 값을 고르는 것도 빼는
것도 판단이고, 판단은 사람의 몫이다. 모순 안건이 걸린 절은 대조 블록으로
내되, 거기서도 후보를 claim_id 순으로 나란히 놓을 뿐 어느 값도 앞세우지
않는다.

사람이 반려한 블록은 같은 내용이면 다시 싣지 않는다. 반려는 그 내용에
대한 결정이므로 같은 문장을 또 올리면 검토자가 같은 일을 되풀이한다.
판정이 블록 지문에 매여 있어 내용이 바뀌면 그 블록은 다시 올라온다.

다만 대조 블록이 그렇게 빠지면 그 안건은 열린 질문으로 되살린다. 대조로
나간 안건은 열린 질문에서 이미 빠져 있어, 대조까지 사라지면 계류인 안건이
검수 표면 어디에도 보이지 않게 된다. 반려된 것은 "이 값들을 이렇게 대조로
보여 주는 방식"이지 "이 안건을 닫는다"가 아니다.

열린 질문은 각색하지 않는다. 판정기가 남긴 summary와 resolver_metadata의
값·근거를 그대로 옮긴다. Compiler가 요약을 다시 쓰면 사람이 보는 문장과
검토 큐의 근거가 달라진다.

블록은 곧 Read Set이다. 모든 블록이 자기 본문의 근거가 된 claim과
proposal을 가리키므로, 저장 전에 그 계약을 이 자리에서 먼저 검사한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_OPEN_QUESTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import ContestedVariant
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.temporal import claim_not_closed_at
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict
from catchup.knowledge_maintenance.ports.artifacts import ArtifactRepository
from catchup.knowledge_maintenance.ports.block_verdicts import BlockVerdictRepository
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredPendingProposal
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

# entity 하나를 설명하는 요약 카드의 문서 종류다.
ARTIFACT_KIND_ENTITY_SUMMARY = "entity_summary"

# 값이 갈렸음을 알리는 계류 안건의 종류다.
PROPOSAL_KIND_CONTRADICTION = "contradiction"


class ArtifactCompileUnitOfWork(Protocol):
    """카드 컴파일이 쓰는 transaction 경계를 정의한다."""

    artifacts: ArtifactRepository
    knowledge_candidates: KnowledgeCandidateRepository
    mutation_proposals: MutationProposalRepository
    block_verdicts: BlockVerdictRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ArtifactCompileResult:
    """카드 컴파일 한 번의 집계를 표현한다.

    Attributes:
        nodes_considered: 이번 실행이 살펴본 대상 노드 수를 나타낸다.
        proposals_created: 계류 변경안이 없던 문서에 새로 올린 수를
            나타낸다.
        proposals_revived: 낡은 계류 변경안을 접고 그 자리를 대신해 올린
            수를 나타낸다. 저장소는 접힌 행을 되살렸는지 돌려주지 않으므로
            서비스가 볼 수 있는 "갱신"으로 센다.
        proposals_abandoned: 낡아서 접은 계류 변경안 수를 나타낸다.
        unchanged_skipped: 지문이 그대로라 아무것도 쓰지 않은 문서 수를
            나타낸다.
        proposals_conflicted: 멱등 키가 이미 결정된 변경안과 부딪혀
            건너뛴 문서 수를 나타낸다.
        blocks_suppressed: 사람이 반려한 내용과 지문이 같아 카드에서 뺀
            블록 수를 나타낸다.
    """

    nodes_considered: int = 0
    proposals_created: int = 0
    proposals_revived: int = 0
    proposals_abandoned: int = 0
    unchanged_skipped: int = 0
    proposals_conflicted: int = 0
    blocks_suppressed: int = 0


def compile_entity_artifacts(
    uow: ArtifactCompileUnitOfWork,
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
    limit: int = 2,
) -> ArtifactCompileResult:
    """claim이 많은 entity의 요약 카드를 변경안으로 올린다.

    어휘 사전은 호출자가 스냅샷에서 읽어 넘긴다. 어느 판본으로 카드를
    만들었는지가 블록에 남아야 하고, 그 판본을 고르는 일은 실행을
    시작하는 쪽의 결정이기 때문이다.

    한 노드가 실패해도 나머지 노드의 작업은 살린다. 커밋이 루프 끝에
    한 번뿐이라 예외가 그대로 올라가면 다른 노드의 카드까지 통째로
    되돌아가기 때문이다. 승인된 옛 판 내용으로의 회귀 제안은 현재 멱등
    키 설계상 자동 재제안이 불가능하므로 그 노드만 건너뛰고 센다. 사람이
    그 회귀를 다시 볼 값어치가 있는지는 후속 스펙 판단으로 남긴다.
    """
    created = 0
    revived = 0
    abandoned = 0
    skipped = 0
    conflicted = 0
    suppressed = 0
    now = datetime.now(timezone.utc)
    with uow:
        sources = uow.artifacts.find_top_entity_nodes(limit=limit)
        claims = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )
        by_node = _group_claims_by_node(claims)

        for source in sources:
            node_claims = by_node.get(source.node_id, ())
            pending = uow.mutation_proposals.find_pending_for_subject_node(
                workspace_id=workspace_id,
                node_id=source.node_id,
            )
            blocks = _build_blocks(
                claims=node_claims,
                pending=pending,
                vocabulary=vocabulary,
                now=now,
            )
            if not blocks:
                # 쓸 내용이 없으면 빈 카드를 만들지 않는다. 검토자에게
                # 보여 줄 문장이 하나도 없기 때문이다.
                logger.info(
                    "artifact_compile_node_empty",
                    workspace_id=workspace_id,
                    node_id=str(source.node_id),
                )
                continue

            # 근거 없는 문장을 막는 첫 자리다. 저장 계층도 같은 검사를
            # 하지만 서비스가 먼저 잡아야 잘못된 블록이 transaction에
            # 실리지 않는다.
            validate_blocks(blocks)
            # 반려 판정은 문서에 매여 있으므로 문서를 먼저 확보한다.
            artifact_id = uow.artifacts.get_or_create_artifact(
                kind=ARTIFACT_KIND_ENTITY_SUMMARY,
                subject_node_id=source.node_id,
                title=source.display_name,
            )
            rejected = uow.block_verdicts.find_rejected_hashes(
                artifact_id=artifact_id,
            )
            blocks, dropped, suppressed_ids = _drop_rejected_blocks(
                blocks,
                rejected,
                workspace_id=workspace_id,
                artifact_id=artifact_id,
            )
            suppressed += dropped
            reopened, dropped_again, _ = _drop_rejected_blocks(
                _revive_suppressed_questions(
                    blocks,
                    pending=pending,
                    suppressed_ids=suppressed_ids,
                    ontology_version=vocabulary.snapshot_id or None,
                ),
                rejected,
                workspace_id=workspace_id,
                artifact_id=artifact_id,
            )
            # 되살린 열린 질문도 같은 반려 장부를 거친다. 그 형태까지
            # 사람이 반려했다면 되살릴 것이 아니라 빠져야 한다.
            suppressed += dropped_again
            if reopened:
                validate_blocks(reopened)
                blocks = (*blocks, *reopened)
            if not blocks:
                # 남은 문장이 없으면 빈 카드 규칙과 같이 건너뛴다. 다만
                # 큐에 남은 계류는 접는다. 그 계류가 담은 본문이 바로
                # 방금 반려된 내용이라, 두면 사람이 같은 것을 또 본다.
                abandoned += uow.artifacts.abandon_pending_proposals(
                    artifact_id=artifact_id,
                )
                logger.info(
                    "artifact_compile_node_all_blocks_suppressed",
                    workspace_id=workspace_id,
                    node_id=str(source.node_id),
                    artifact_id=str(artifact_id),
                    blocks_suppressed=dropped,
                )
                continue

            content_hash = blocks_content_hash(blocks)
            known = uow.artifacts.find_latest_content_hashes(
                artifact_id=artifact_id,
            )
            if content_hash in known:
                skipped += 1
                abandoned += _abandon_stale_pending(
                    uow,
                    artifact_id=artifact_id,
                    content_hash=content_hash,
                )
                continue

            replaced = uow.artifacts.abandon_pending_proposals(
                artifact_id=artifact_id,
            )
            abandoned += replaced
            latest = uow.artifacts.find_latest_revision_id_and_number(
                artifact_id=artifact_id,
            )
            base_revision_id = None if latest is None else latest[0]
            try:
                proposal_id = uow.artifacts.add_or_revive_proposal(
                    artifact_id=artifact_id,
                    blocks=blocks,
                    content_hash=content_hash,
                    idempotency_key=artifact_idempotency_key(
                        artifact_id,
                        content_hash,
                        base_revision_id=base_revision_id,
                    ),
                    base_revision_id=base_revision_id,
                )
            except ArtifactProposalConflict:
                # 키에 기준 판이 들어가므로 정상 흐름에서는 결정된 행과
                # 부딪히지 않는다. 그래도 부딪히면 데이터 이상 신호이므로
                # 이 노드만 건너뛰고 나머지 노드의 작업은 그대로 커밋한다.
                # 바로 위에서 접은 계류는 되돌리지 않는다.
                conflicted += 1
                logger.warning(
                    "artifact_compile_proposal_conflict",
                    workspace_id=workspace_id,
                    node_id=str(source.node_id),
                    artifact_id=str(artifact_id),
                    content_hash=content_hash,
                )
                continue
            if replaced:
                revived += 1
            else:
                created += 1
            logger.info(
                "artifact_compile_proposed",
                workspace_id=workspace_id,
                node_id=str(source.node_id),
                artifact_id=str(artifact_id),
                proposal_id=str(proposal_id),
                block_count=len(blocks),
                replaced_pending=replaced,
            )

        uow.commit()

    result = ArtifactCompileResult(
        nodes_considered=len(sources),
        proposals_created=created,
        proposals_revived=revived,
        proposals_abandoned=abandoned,
        unchanged_skipped=skipped,
        proposals_conflicted=conflicted,
        blocks_suppressed=suppressed,
    )
    logger.info(
        "artifact_compile_completed",
        workspace_id=workspace_id,
        nodes_considered=result.nodes_considered,
        proposals_created=result.proposals_created,
        proposals_revived=result.proposals_revived,
        proposals_abandoned=result.proposals_abandoned,
        unchanged_skipped=result.unchanged_skipped,
        proposals_conflicted=result.proposals_conflicted,
        blocks_suppressed=result.blocks_suppressed,
    )
    return result


def _drop_rejected_blocks(
    blocks: Sequence[ArtifactBlock],
    rejected: Mapping[str, str],
    *,
    workspace_id: int,
    artifact_id: uuid.UUID,
) -> tuple[tuple[ArtifactBlock, ...], int, frozenset[uuid.UUID]]:
    """사람이 반려한 내용과 지문이 같은 블록을 뺀다.

    반려는 그 내용에 대한 결정이므로, 같은 내용이 다시 컴파일돼 올라오면
    사람이 같은 것을 또 보게 된다. 그것이 좀비 블록이다. 판정은 블록
    지문에 매여 있으니 내용이 한 글자라도 바뀌면 지문이 달라져 그 블록은
    다시 검토 큐에 오른다. 반려를 영구 삭제로 굳히지 않는 장치다.

    남은 블록·뺀 수와 함께, 빠진 블록이 가리키던 안건 식별자를 돌려준다.
    그 안건이 검수 표면에서 통째로 사라지지 않게 하려면 무엇이 함께
    빠졌는지 호출자가 알아야 한다.
    """
    if not rejected:
        return tuple(blocks), 0, frozenset()
    kept: list[ArtifactBlock] = []
    dropped = 0
    suppressed_ids: set[uuid.UUID] = set()
    for block in blocks:
        digest = block_content_hash(block)
        reason = rejected.get(digest)
        if reason is None:
            kept.append(block)
            continue
        dropped += 1
        suppressed_ids.update(block.proposal_ids)
        logger.info(
            "artifact_compile_block_suppressed",
            workspace_id=workspace_id,
            artifact_id=str(artifact_id),
            block_hash=digest,
            reason=reason,
        )
    return tuple(kept), dropped, frozenset(suppressed_ids)


def _revive_suppressed_questions(
    kept: Sequence[ArtifactBlock],
    *,
    pending: Sequence[StoredPendingProposal],
    suppressed_ids: frozenset[uuid.UUID],
    ontology_version: str | None,
) -> tuple[ArtifactBlock, ...]:
    """반려로 빠진 블록이 데려간 모순 안건을 열린 질문으로 되살린다.

    대조로 나간 안건은 `_build_blocks`가 열린 질문에서 이미 뺐다. 그
    대조 블록마저 반려로 빠지면 계류인 안건이 카드 어디에도 없게 되어,
    검토자가 그 안건을 다시 만날 길이 사라진다. 반려된 것은 대조라는
    표현 방식이지 안건 자체가 아니므로 열린 질문 형태로 다시 올린다.

    아직 남은 블록이 가리키는 안건은 되살리지 않는다. 같은 안건이 카드에
    두 번 나오면 검토자가 한 결정을 두 자리에서 내려야 한다.

    순서는 `_open_questions`가 정한 그대로다. 정렬 규칙을 여기서 새로
    만들면 같은 입력이 다른 본문을 낳는다.
    """
    if not suppressed_ids:
        return ()
    still_shown = {
        proposal_id
        for block in kept
        for proposal_id in block.proposal_ids
    }
    revived = [
        proposal
        for proposal in pending
        if proposal.proposal_kind == PROPOSAL_KIND_CONTRADICTION
        and proposal.id in suppressed_ids
        and proposal.id not in still_shown
    ]
    return tuple(_open_questions(revived, ontology_version))


def _abandon_stale_pending(
    uow: ArtifactCompileUnitOfWork,
    *,
    artifact_id: uuid.UUID,
    content_hash: str,
) -> int:
    """넘어가는 문서에 남은, 내용이 다른 계류 변경안을 접는다.

    지문이 그대로라 이번에 쓸 것이 없어도 큐에 내용이 다른 변경안이
    남아 있을 수 있다. 그것을 사람이 나중에 승인하면 지금 컴파일한
    본문과 다른 판이 발행되므로 여기서 접는다.

    지금 지문과 같은 계류가 있으면 아무것도 접지 않는다. 그 행이 곧
    이번 내용이라 접으면 검토 큐가 이유 없이 비기 때문이다.
    """
    hashes = {
        proposal.content_hash
        for proposal in uow.artifacts.list_pending_proposals()
        if proposal.artifact_id == artifact_id
    }
    if not hashes or content_hash in hashes:
        return 0
    return uow.artifacts.abandon_pending_proposals(artifact_id=artifact_id)


def _group_claims_by_node(
    claims: Iterable[StoredClaimCandidate],
) -> dict[uuid.UUID, list[StoredClaimCandidate]]:
    """claim을 subject 노드별로 모은다.

    subject는 canonical 노드를 직접 가리키거나 해소를 마친 entity 후보를
    거쳐 가리킨다. 두 경로를 합쳐 세지 않으면 대부분의 카드가 빈다.
    """
    grouped: dict[uuid.UUID, list[StoredClaimCandidate]] = {}
    for claim in claims:
        node_id = claim.subject_node_id or claim.subject_resolved_node_id
        if node_id is None:
            continue
        grouped.setdefault(node_id, []).append(claim)
    return grouped


def _build_blocks(
    *,
    claims: Sequence[StoredClaimCandidate],
    pending: Sequence[StoredPendingProposal],
    vocabulary: ExtractionVocabulary,
    now: datetime,
) -> tuple[ArtifactBlock, ...]:
    """카드 본문을 이룰 블록을 정해진 순서로 만든다.

    대조로 실린 모순 안건은 열린 질문에서 뺀다. 같은 안건이 카드에 두 번
    나오면 검토자가 한 결정을 두 자리에서 내려야 하기 때문이다.
    """
    ontology_version = vocabulary.snapshot_id or None
    sections = _claim_sections(
        claims,
        vocabulary,
        ontology_version,
        now,
        _contradictions(pending),
    )
    contested_ids = {
        proposal_id
        for block in sections
        if block.block_kind == BLOCK_KIND_CONTESTED
        for proposal_id in block.proposal_ids
    }
    questions = _open_questions(
        [item for item in pending if item.id not in contested_ids],
        ontology_version,
    )
    return tuple([*sections, *questions])


@dataclass(frozen=True, slots=True)
class _Contradiction:
    """모순 안건 하나와 그 안건이 다루는 claim 집합을 담는다.

    Attributes:
        proposal: 계류 중인 모순 안건을 가리킨다.
        claim_ids: 안건의 판정 근거가 가리키는 claim들을 나타낸다.
    """

    proposal: StoredPendingProposal
    claim_ids: frozenset[uuid.UUID]


def _contradictions(
    pending: Sequence[StoredPendingProposal],
) -> tuple[_Contradiction, ...]:
    """모순 안건과 그 안건이 다루는 claim 집합을 짝지어 모은다.

    안건 순서를 식별자로 고정한다. 한 절에 걸리는 안건이 여럿일 때 어느
    것을 대조로 낼지도 이 순서로 정해지는데, 어느 안건이 더 중요한지는
    컴파일러가 판단할 일이 아니므로 내용과 무관한 기준만 쓴다.
    """
    return tuple(
        _Contradiction(
            proposal=proposal,
            claim_ids=frozenset(
                _claim_ids_in(_metadata_values(proposal.resolver_metadata))
            ),
        )
        for proposal in sorted(pending, key=lambda item: str(item.id))
        if proposal.proposal_kind == PROPOSAL_KIND_CONTRADICTION
    )


def _claim_sections(
    claims: Sequence[StoredClaimCandidate],
    vocabulary: ExtractionVocabulary,
    ontology_version: str | None,
    now: datetime,
    contradictions: Sequence[_Contradiction],
) -> list[ArtifactBlock]:
    """predicate별 claim_section 블록을 사전 순서대로 만든다.

    사전에 등재된 predicate가 사전이 정의한 순서로 먼저 오고, 미등재
    predicate가 이름순으로 뒤를 잇는다. 사전 순서는 사람이 정한 읽는
    순서이므로 그것이 카드의 순서가 된다. 미등재를 이름순으로 두는 것은
    기댈 순서가 이름밖에 없기 때문이다.

    now 시점에 구간이 닫힌 주장은 싣지 않는다. 문서의 현재 판은 지금
    믿는 것을 말해야 하기 때문이다. 지나간 값은 claim 행과 옛 판에
    그대로 남아 있으므로 사라지는 것이 아니다. 발효 예정(valid_from이
    미래)인 주장은 거르지 않는다 — 판정 정의는 `domain.temporal`이
    단독으로 갖는다.

    모순 안건이 걸린 predicate는 대조 블록을 앞세운다. 값을 줄로 늘어놓기만
    하면 검토자가 어느 것을 고를지 결정할 자리가 카드에 없기 때문이다.
    여기서도 값을 고르지는 않는다 — 후보를 나란히 놓을 뿐이다.

    대조에 들어가는 것은 그 안건이 가리키는 claim뿐이다. 같은 predicate에
    있어도 안건이 다루지 않는 값까지 후보로 넣으면, 검토자가 안건 밖의
    claim을 승자로 고를 수 있게 되어 결정을 적용하는 쪽 계약이 깨진다.
    안건 밖의 값들은 같은 제목의 claim_section으로 대조 블록 뒤에 잇는다.
    """
    grouped: dict[str, list[StoredClaimCandidate]] = {}
    for claim in claims:
        if not claim_not_closed_at(claim.valid_to, now):
            continue
        grouped.setdefault(claim.predicate, []).append(claim)

    order = {
        entry.name: index
        for index, entry in enumerate(vocabulary.predicate_entries)
    }
    sections: list[ArtifactBlock] = []
    for predicate in sorted(
        grouped,
        key=lambda name: (
            (0, order[name], "") if name in order else (1, 0, name)
        ),
    ):
        members = sorted(
            grouped[predicate],
            key=lambda claim: (claim.observed_at, claim.id),
        )
        picked = _contested_pick(members, contradictions)
        if picked is not None:
            proposal, disputed = picked
            sections.append(
                _contested_block(
                    predicate=predicate,
                    members=disputed,
                    proposal=proposal,
                    ontology_version=ontology_version,
                )
            )
            taken = {claim.id for claim in disputed}
            members = [
                claim for claim in members if claim.id not in taken
            ]
            if not members:
                continue
        sections.append(
            ArtifactBlock(
                block_kind=BLOCK_KIND_CLAIM_SECTION,
                heading=predicate,
                body="\n".join(_claim_line(claim) for claim in members),
                claim_ids=tuple(claim.id for claim in members),
                proposal_ids=(),
                ontology_version=ontology_version,
                sources=tuple(_claim_source(claim) for claim in members),
            )
        )
    return sections


def _claim_line(claim: StoredClaimCandidate) -> str:
    """claim 하나를 원본 값과 관찰 날짜 그대로 한 줄로 적는다."""
    return f"{claim.value} ({claim.observed_at:%Y-%m-%d} 관찰)"


def _claim_source(claim: StoredClaimCandidate) -> BlockSource:
    """claim의 저장된 인용을 블록 근거로 옮긴다."""
    return BlockSource(
        claim_id=claim.id,
        statement=claim.statement,
        observed_at=claim.observed_at,
        citation_verified=claim.citation_verified,
    )


def _contested_pick(
    members: Sequence[StoredClaimCandidate],
    contradictions: Sequence[_Contradiction],
) -> tuple[StoredPendingProposal, tuple[StoredClaimCandidate, ...]] | None:
    """이 절을 대조로 낼 안건과 그 후보 claim을 고른다. 없으면 None이다.

    후보는 안건이 가리키는 claim과 살아 있는 값의 교집합이다. 그 교집합이
    둘 미만이면 대조가 성립하지 않으므로 평범한 절로 두고, 안건은 열린
    질문으로 그대로 남긴다. 한쪽 값이 닫힌 뒤에도 안건이 열려 있는 경우가
    그렇다.
    """
    if len(members) < 2:
        return None
    for contradiction in contradictions:
        disputed = tuple(
            claim for claim in members if claim.id in contradiction.claim_ids
        )
        if len(disputed) >= 2:
            return (contradiction.proposal, disputed)
    return None


def _contested_block(
    *,
    predicate: str,
    members: Sequence[StoredClaimCandidate],
    proposal: StoredPendingProposal,
    ontology_version: str | None,
) -> ArtifactBlock:
    """상충하는 값들을 후보로 나란히 놓은 대조 블록을 만든다.

    후보 순서는 claim_id 사전순으로 고정한다. 관찰 시각이나 값으로 줄을
    세우면 컴파일러가 최신 값이나 특정 값을 앞세우는 셈이 되는데, 어느
    값이 맞는지 고르는 일은 사람의 몫이다.
    """
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CONTESTED,
        heading=predicate,
        body=f"상충하는 값 {len(members)}개 — 검토 필요",
        claim_ids=tuple(claim.id for claim in members),
        proposal_ids=(proposal.id,),
        ontology_version=ontology_version,
        sources=tuple(_claim_source(claim) for claim in members),
        variants=tuple(
            ContestedVariant(
                claim_id=claim.id,
                body=_claim_line(claim),
                sources=(_claim_source(claim),),
            )
            for claim in sorted(members, key=lambda item: str(item.id))
        ),
    )


def _open_questions(
    pending: Sequence[StoredPendingProposal],
    ontology_version: str | None,
) -> list[ArtifactBlock]:
    """계류 안건마다 열린 질문 블록을 만든다.

    안건 순서를 종류와 식별자로 고정한다. 저장소가 돌려주는 순서에
    기대면 같은 입력이 다른 본문을 낳을 수 있기 때문이다.
    """
    blocks: list[ArtifactBlock] = []
    for proposal in sorted(
        pending, key=lambda item: (item.proposal_kind, item.id)
    ):
        values = _metadata_values(proposal.resolver_metadata)
        lines = [proposal.summary, *(_value_line(item) for item in values)]
        blocks.append(
            ArtifactBlock(
                block_kind=BLOCK_KIND_OPEN_QUESTION,
                heading=f"열린 질문: {proposal.proposal_kind}",
                body="\n".join(line for line in lines if line),
                claim_ids=_claim_ids_in(values),
                proposal_ids=(proposal.id,),
                ontology_version=ontology_version,
                sources=_value_sources(values),
            )
        )
    return blocks


def _metadata_values(
    metadata: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    """판정 근거에 담긴 값 후보 목록을 꺼낸다.

    모순 안건만 값 목록을 남긴다. 다른 종류이거나 낡은 metadata라 모양이
    다르면 빈 목록으로 본다. 카드가 깨지는 것보다 요약만 싣는 편이 낫다.
    """
    values = metadata.get("values")
    if not isinstance(values, list):
        return ()
    return tuple(item for item in values if isinstance(item, Mapping))


def _value_line(item: Mapping[str, object]) -> str:
    """값 후보 하나를 원본 값과 관찰 시각 그대로 한 줄로 적는다."""
    value = item.get("value")
    observed_at = _observed_date(item.get("observed_at"))
    if observed_at is None:
        return f"- {value}"
    return f"- {value} ({observed_at} 관찰)"


def _observed_date(raw: object) -> str | None:
    """저장된 관찰 시각을 날짜 문자열로 바꾼다. 읽지 못하면 None이다."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return f"{datetime.fromisoformat(raw):%Y-%m-%d}"
    except ValueError:
        # 낡은 metadata가 ISO 형식이 아니면 원문을 그대로 보여 준다.
        return raw


def _observed_moment(raw: object) -> datetime | None:
    """저장된 관찰 시각을 시점으로 읽는다. 읽지 못하면 None이다.

    본문 한 줄을 적는 `_observed_date`는 읽지 못한 값을 원문 그대로
    보여 주지만, 근거 인용의 observed_at은 시점이어야 하므로 여기서는
    실패를 None으로 알린다.
    """
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _claim_ids_in(
    values: Sequence[Mapping[str, object]],
) -> tuple[uuid.UUID, ...]:
    """값 후보가 가리키는 근거 claim을 순서대로 모은다."""
    found: list[uuid.UUID] = []
    for item in values:
        claim_id = _claim_id_of(item)
        if claim_id is None:
            continue
        if claim_id not in found:
            found.append(claim_id)
    return tuple(found)


def _claim_id_of(item: Mapping[str, object]) -> uuid.UUID | None:
    """값 후보가 가리키는 claim 식별자를 읽는다. 못 읽으면 None이다."""
    raw = item.get("claim_id")
    if not isinstance(raw, str):
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _value_sources(
    values: Sequence[Mapping[str, object]],
) -> tuple[BlockSource, ...]:
    """값 후보의 근거 인용을 값 후보 순서대로 모은다.

    claim·인용 문장·관찰 시점을 모두 읽을 수 있는 후보만 싣는다. 낡은
    metadata에 어느 하나가 빠져 있으면 그 후보의 인용만 빠뜨리고 넘어간다.
    카드 전체가 깨지는 것보다 낫다는 기존 방침을 따른다. 그래서 인용 수는
    본문 줄 수보다 적을 수 있다 — 열린 질문 블록에서 인용과 본문 줄은
    1:1이 아니다.

    대조 판정은 None으로 둔다. 값이 없어서가 아니다.
    `resolve_claim_conflicts`가 값 후보마다 `citation_verified`를 실제로
    적어 두므로 metadata에는 값이 있다. 이 슬라이스가 스펙대로 그 실값
    배선을 보류했을 뿐이고, 배선은 별도 백로그로 남았다. 그때까지 열린
    질문의 인용은 evidence 없음으로 보인다.
    """
    sources: list[BlockSource] = []
    for item in values:
        claim_id = _claim_id_of(item)
        statement = item.get("statement")
        observed_at = _observed_moment(item.get("observed_at"))
        if claim_id is None or observed_at is None:
            continue
        if not isinstance(statement, str) or not statement:
            continue
        sources.append(
            BlockSource(
                claim_id=claim_id,
                statement=statement,
                observed_at=observed_at,
                citation_verified=None,
            )
        )
    return tuple(sources)
