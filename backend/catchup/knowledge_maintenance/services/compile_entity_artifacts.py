"""canonical entity의 요약 카드를 결정론으로 컴파일한다.

LLM을 부르지 않는다. 카드는 이미 저장된 claim과 계류 중인 안건을 정해진
순서로 늘어놓은 것뿐이고, 같은 입력이면 같은 본문이 나와야 한다. 본문이
실행마다 흔들리면 내용 지문이 매번 달라져 사람이 이미 본 카드가 검토
큐에 다시 쌓인다.

값을 고르지 않는다. 한 predicate에 값이 여럿이면 전부 나열하고, 어느
값이 맞는지 묻는 일은 열린 질문 블록이 맡는다. 값을 고르는 것도 빼는
것도 판단이고, 판단은 사람의 몫이다. 그래서 모순 안건이 열려 있어도
claim_section은 값을 그대로 남긴다.

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
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_OPEN_QUESTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict
from catchup.knowledge_maintenance.ports.artifacts import ArtifactRepository
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


class ArtifactCompileUnitOfWork(Protocol):
    """카드 컴파일이 쓰는 transaction 경계를 정의한다."""

    artifacts: ArtifactRepository
    knowledge_candidates: KnowledgeCandidateRepository
    mutation_proposals: MutationProposalRepository

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
    """

    nodes_considered: int = 0
    proposals_created: int = 0
    proposals_revived: int = 0
    proposals_abandoned: int = 0
    unchanged_skipped: int = 0
    proposals_conflicted: int = 0


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
            content_hash = blocks_content_hash(blocks)
            artifact_id = uow.artifacts.get_or_create_artifact(
                kind=ARTIFACT_KIND_ENTITY_SUMMARY,
                subject_node_id=source.node_id,
                title=source.display_name,
            )
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
            try:
                proposal_id = uow.artifacts.add_or_revive_proposal(
                    artifact_id=artifact_id,
                    blocks=blocks,
                    content_hash=content_hash,
                    idempotency_key=artifact_idempotency_key(
                        artifact_id, content_hash
                    ),
                    base_revision_id=None if latest is None else latest[0],
                )
            except ArtifactProposalConflict:
                # 사람이 이미 결정한 행이 같은 키를 쓰고 있다. 이 노드만
                # 건너뛰고 나머지 노드의 작업은 그대로 커밋한다. 바로 위에서
                # 접은 계류는 되돌리지 않는다. 그 내용은 이미 낡았다.
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
    )
    return result


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
) -> tuple[ArtifactBlock, ...]:
    """카드 본문을 이룰 블록을 정해진 순서로 만든다."""
    ontology_version = vocabulary.snapshot_id or None
    blocks = [
        *_claim_sections(claims, vocabulary, ontology_version),
        *_open_questions(pending, ontology_version),
    ]
    return tuple(blocks)


def _claim_sections(
    claims: Sequence[StoredClaimCandidate],
    vocabulary: ExtractionVocabulary,
    ontology_version: str | None,
) -> list[ArtifactBlock]:
    """predicate별 claim_section 블록을 사전 순서대로 만든다.

    사전에 등재된 predicate가 사전이 정의한 순서로 먼저 오고, 미등재
    predicate가 이름순으로 뒤를 잇는다. 사전 순서는 사람이 정한 읽는
    순서이므로 그것이 카드의 순서가 된다. 미등재를 이름순으로 두는 것은
    기댈 순서가 이름밖에 없기 때문이다.
    """
    grouped: dict[str, list[StoredClaimCandidate]] = {}
    for claim in claims:
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
        sections.append(
            ArtifactBlock(
                block_kind=BLOCK_KIND_CLAIM_SECTION,
                heading=predicate,
                body="\n".join(
                    f"{claim.value} ({claim.observed_at:%Y-%m-%d} 관찰)"
                    for claim in members
                ),
                claim_ids=tuple(claim.id for claim in members),
                proposal_ids=(),
                ontology_version=ontology_version,
            )
        )
    return sections


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


def _claim_ids_in(
    values: Sequence[Mapping[str, object]],
) -> tuple[uuid.UUID, ...]:
    """값 후보가 가리키는 근거 claim을 순서대로 모은다."""
    found: list[uuid.UUID] = []
    for item in values:
        raw = item.get("claim_id")
        if not isinstance(raw, str):
            continue
        try:
            claim_id = uuid.UUID(raw)
        except ValueError:
            continue
        if claim_id not in found:
            found.append(claim_id)
    return tuple(found)
