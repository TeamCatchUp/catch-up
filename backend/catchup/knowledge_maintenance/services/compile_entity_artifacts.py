"""canonical entity의 요약 카드를 결정론으로 컴파일한다.

블록의 구성은 LLM을 부르지 않는다. 어떤 블록이 어떤 근거로 서는지는 이미
저장된 claim과 계류 안건을 정해진 순서로 늘어놓은 것뿐이고, 같은 입력이면
같은 블록이 나와야 한다. 본문이 실행마다 흔들리면 내용 지문이 매번 달라져
사람이 이미 본 카드가 검토 큐에 다시 쌓인다.

블록 위에 얹는 산문만 밖에서 받는다. 산문은 근거가 아니라 표현이라 내용
지문에서 빠지고, 내용이 그대로인 블록은 지난 문장을 그대로 다시 쓴다.
narrator를 주지 않으면 산문 없이 종전대로 컴파일한다.

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
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timezone
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.domain.actor_identity import actor_display
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_OPEN_QUESTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import SUMMARY_SECTION_KEYS
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import ContestedVariant
from catchup.knowledge_maintenance.domain.artifact import artifact_idempotency_key
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpecError
from catchup.knowledge_maintenance.domain.artifact_definition import (
    validate_selection_spec,
)
from catchup.knowledge_maintenance.domain.block_diff import CHANGE_MODIFIED
from catchup.knowledge_maintenance.domain.block_diff import diff_blocks
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.preset_catalog import DEFAULT_PURPOSE_SENTENCE
from catchup.knowledge_maintenance.domain.preset_catalog import (
    DEFAULT_STYLE_INSTRUCTION,
)
from catchup.knowledge_maintenance.domain.preset_catalog import find_actor_exposure
from catchup.knowledge_maintenance.domain.preset_catalog import find_kind_by_name
from catchup.knowledge_maintenance.domain.preset_catalog import find_purpose
from catchup.knowledge_maintenance.domain.preset_catalog import find_style
from catchup.knowledge_maintenance.domain.temporal import claim_not_closed_at
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    ArtifactDefinitionRepository,
)
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    StoredArtifactDefinition,
)
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict
from catchup.knowledge_maintenance.ports.artifacts import ArtifactRepository
from catchup.knowledge_maintenance.ports.artifacts import EntityCardSource
from catchup.knowledge_maintenance.ports.block_verdicts import BlockVerdictRepository
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredPendingProposal
from catchup.knowledge_maintenance.ports.narrator import BlockNarrationInput
from catchup.knowledge_maintenance.ports.narrator import BlockNarrator
from catchup.knowledge_maintenance.ports.narrator import ChangeExplanationRequest
from catchup.knowledge_maintenance.ports.narrator import DocumentNarrationRequest
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.knowledge_maintenance.ports.relations import RelationRepository
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
from catchup.knowledge_maintenance.services.traverse_relations import (
    RELATION_HINT_PREFIX,
)
from catchup.knowledge_maintenance.services.traverse_relations import EdgeFormatter
from catchup.knowledge_maintenance.services.traverse_relations import format_edge_line
from catchup.knowledge_maintenance.services.traverse_relations import (
    relation_section_block,
)
from catchup.knowledge_maintenance.services.traverse_relations import (
    traverse_relation_path,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

# 값이 갈렸음을 알리는 계류 안건의 종류다.
PROPOSAL_KIND_CONTRADICTION = "contradiction"

# 머리말 재료에 붙이는 블록 번호다. 머리말은 요청의 blocks에 서지 않고
# summary 한 칸으로 실려 응답도 번호로 오지 않으므로, 본문 블록의 연번과
# 섞이지 않도록 음수를 쓴다.
_SUMMARY_BLOCK_ID = -1


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


class DefinitionCompileUnitOfWork(ArtifactCompileUnitOfWork, Protocol):
    """정의 순회 컴파일이 쓰는 transaction 경계를 정의한다.

    카드 컴파일이 쓰던 저장소에 정의와 관계를 더한다. 입구가 정의 목록
    이고 본문에 관계 절이 서므로, 두 저장소 없이는 이 컴파일이 성립하지
    않는다.
    """

    artifact_definitions: ArtifactDefinitionRepository
    relations: RelationRepository


class RelationPathTruncatedError(RuntimeError):
    """잘린 경로에서 완주한 가지가 없어 문서를 세울 수 없음을 나타낸다.

    Attributes:
        path_index: 정의에 적힌 경로 중 몇 번째에서 났는지 나타낸다.
        truncated_steps: 그 경로에서 잘린 걸음 번호들을 나타낸다.
    """

    def __init__(
        self, *, path_index: int, truncated_steps: tuple[int, ...]
    ) -> None:
        super().__init__(
            f"경로 {path_index}이 잘렸는데 완주한 가지가 없다:"
            f" 잘린 걸음 {list(truncated_steps)}"
        )
        self.path_index = path_index
        self.truncated_steps = truncated_steps


@dataclass(frozen=True, slots=True)
class ArtifactCompileResult:
    """카드 컴파일 한 번의 집계를 표현한다.

    Attributes:
        definitions_considered: 이번 실행이 읽은 정의 수를 나타낸다.
            선택 규칙이 어휘와 어긋나 건너뛴 정의도 읽기는 했으므로
            함께 센다.
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
        nodes_failed: 문서를 세울 수 없어 컴파일을 접은 노드 수를
            나타낸다. 접은 문서만큼 카드가 비므로 호출자가 이 수를 보고
            실행을 실패로 다룰 수 있어야 한다.
        blocks_narrated: 이번 실행이 새로 산문을 받은 블록 수를
            나타낸다. 성공한 노드의 서술 수다 — 서술 도중 접힌 노드의
            중간 집계는 버리므로 실제 LLM 호출 수보다 작을 수 있다.
        blocks_narrative_reused: 지난 산문을 그대로 다시 쓴 블록 수를
            나타낸다. 이 수가 클수록 검수자가 볼 산문 diff가 작다.
        blocks_explained: 이번 실행이 새로 수정 이유를 받은 블록 수를
            나타낸다. 발행 판과 짝이 맞으면서 내용이 달라진 블록만 센다.
        blocks_explanation_reused: 지난 수정 이유를 그대로 다시 쓴 블록
            수를 나타낸다.
    """

    definitions_considered: int = 0
    nodes_considered: int = 0
    proposals_created: int = 0
    proposals_revived: int = 0
    proposals_abandoned: int = 0
    unchanged_skipped: int = 0
    proposals_conflicted: int = 0
    blocks_suppressed: int = 0
    nodes_failed: int = 0
    blocks_narrated: int = 0
    blocks_narrative_reused: int = 0
    blocks_explained: int = 0
    blocks_explanation_reused: int = 0


def compile_definition_artifacts(
    uow: DefinitionCompileUnitOfWork,
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
    narrator: BlockNarrator | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ArtifactCompileResult:
    """workspace의 정의를 돌며 정의가 고른 문서를 변경안으로 올린다.

    무엇을 문서로 만들지는 사람이 채널에 걸어 둔 정의가 정한다. 몇 개를
    만들지 고르는 자리가 없으므로 상한 인자도 없다 — 정의가 고른 노드는
    전부 대상이며, 그중 일부만 만들면 같은 정의가 실행마다 다른 문서
    묶음을 낳는다.

    정의 하나가 어휘와 어긋나면 그 정의만 건너뛴다. 어휘 개정으로
    이름이 사라진 정의를 그대로 컴파일하면 조건에 맞는 노드가 없어
    조용히 빈 문서가 되고, 반대로 실행 전체를 세우면 멀쩡한 정의의
    문서까지 함께 멈춘다. 노드 단위 격리와 같은 원칙이다.

    시점은 실행 시작에 한 번 읽어 순회와 claim 판정이 함께 쓴다. 걸음
    마다 시계를 새로 읽으면 같은 실행 안에서도 살아 있는 것의 기준이
    흔들린다. 그 시계는 호출자가 넘길 수 있다. 파이프라인 한 회차를
    이루는 단계들이 같은 시점을 공유해야 단계 사이에서 기준이 어긋나지
    않는다.

    narrator를 주지 않으면 산문 없이 컴파일한다. 산문은 블록 위에 얹는
    표현이라 없어도 문서가 성립하고, 벤치처럼 사람이 읽지 않는 실행은
    부를 이유가 없다.
    """
    created = 0
    revived = 0
    abandoned = 0
    skipped = 0
    conflicted = 0
    suppressed = 0
    nodes_considered = 0
    nodes_failed = 0
    narrated = 0
    reused = 0
    explained = 0
    explanations_reused = 0
    now = (clock or _utcnow)()
    with uow:
        definitions = uow.artifact_definitions.list_definitions()
        claims = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )
        by_node = _group_claims_by_node(claims)

        for definition in definitions:
            try:
                validate_selection_spec(definition.selection_spec, vocabulary)
            except SelectionSpecError as error:
                logger.warning(
                    "artifact_compile_definition_invalid",
                    workspace_id=workspace_id,
                    definition_id=str(definition.id),
                    kind=definition.kind,
                    reason=str(error),
                )
                continue

            style_instruction = _style_instruction(uow, definition, narrator)
            purpose_sentence = _purpose_sentence(uow, definition)
            exposure = _actor_exposure(uow, definition)

            sources = uow.artifacts.find_entity_nodes_by_types(
                entity_types=definition.selection_spec.entity_types,
            )
            nodes_considered += len(sources)
            for source in sources:
                pending = (
                    uow.mutation_proposals.find_pending_for_subject_node(
                        workspace_id=workspace_id,
                        node_id=source.node_id,
                    )
                )
                try:
                    relation_blocks = _relation_blocks(
                        uow,
                        definition=definition,
                        source=source,
                        ontology_version=vocabulary.snapshot_id or None,
                        now=now,
                        exposure=exposure,
                    )
                except RelationPathTruncatedError as error:
                    # 이 문서만 접는다. 정의 하나가 어긋났을 때와 같은
                    # 격리다 — 허브 노드 하나가 그 정의의 카드 전부를
                    # 멈추게 두지 않는다.
                    #
                    # 앞선 실행이 올려 둔 계류 변경안도 함께 거둔다. 그
                    # 행은 검토 큐에 그대로 보이고 자동 승인이 도는
                    # 자리에서는 판으로 확정되므로, 두면 방금 불완전하다고
                    # 판정한 내용이 그 길로 발행된다. 문서를 찾기만 하고
                    # 만들지는 않는다 — 한 번도 선 적 없는 문서를 실패로
                    # 세우면 제목만 있고 내용이 없는 카드가 남는다.
                    dropped = 0
                    existing = uow.artifacts.find_definition_artifact(
                        definition_id=definition.id,
                        subject_node_id=source.node_id,
                    )
                    if existing is not None:
                        dropped = uow.artifacts.abandon_pending_proposals(
                            artifact_id=existing,
                        )
                        abandoned += dropped
                    logger.warning(
                        "artifact_compile_node_failed_truncated_path",
                        workspace_id=workspace_id,
                        definition_id=str(definition.id),
                        node_id=str(source.node_id),
                        path_index=error.path_index,
                        truncated_steps=list(error.truncated_steps),
                        proposals_abandoned=dropped,
                    )
                    nodes_failed += 1
                    continue

                title = _definition_title(definition, source)
                blocks = _build_blocks(
                    claims=by_node.get(source.node_id, ()),
                    pending=pending,
                    vocabulary=vocabulary,
                    now=now,
                    allowed=definition.selection_spec.predicate_sections,
                    relation_blocks=relation_blocks,
                )
                if not blocks:
                    # 쓸 내용이 없으면 빈 문서를 만들지 않는다. 검토자에게
                    # 보여 줄 문장이 하나도 없기 때문이다.
                    logger.info(
                        "artifact_compile_node_empty",
                        workspace_id=workspace_id,
                        definition_id=str(definition.id),
                        node_id=str(source.node_id),
                    )
                    continue

                # 근거 없는 문장을 막는 첫 자리다. 저장 계층도 같은 검사를
                # 하지만 서비스가 먼저 잡아야 잘못된 블록이 transaction에
                # 실리지 않는다.
                validate_blocks(blocks)
                # 반려 판정은 문서에 매여 있으므로 문서를 먼저 확보한다.
                artifact_id = (
                    uow.artifacts.get_or_create_definition_artifact(
                        definition_id=definition.id,
                        channel_id=definition.channel_id,
                        kind=definition.kind,
                        subject_node_id=source.node_id,
                        title=title,
                        folder_id=definition.folder_id,
                    )
                )
                try:
                    outcome = _propose_node_blocks(
                        uow,
                        workspace_id=workspace_id,
                        node_id=source.node_id,
                        artifact_id=artifact_id,
                        blocks=blocks,
                        pending=pending,
                        ontology_version=vocabulary.snapshot_id or None,
                        narrator=narrator,
                        style_instruction=style_instruction,
                        purpose_sentence=purpose_sentence,
                    )
                except NarrationError as error:
                    # 잘림 실패와 같은 격리다. 산문이 반쪽인 문서를
                    # 검수자에게 올리지 않으므로 이 문서만 접고, 앞선
                    # 실행이 남긴 계류도 함께 거둔다. 그 계류를 두면
                    # 방금 세울 수 없다고 판정한 자리가 자동 승인 경로로
                    # 발행된다.
                    dropped = uow.artifacts.abandon_pending_proposals(
                        artifact_id=artifact_id,
                    )
                    abandoned += dropped
                    logger.warning(
                        "artifact_compile_node_failed_narration",
                        workspace_id=workspace_id,
                        definition_id=str(definition.id),
                        node_id=str(source.node_id),
                        artifact_id=str(artifact_id),
                        reason=str(error),
                        proposals_abandoned=dropped,
                    )
                    nodes_failed += 1
                    continue
                created += outcome.created
                revived += outcome.revived
                abandoned += outcome.abandoned
                skipped += outcome.skipped
                conflicted += outcome.conflicted
                suppressed += outcome.suppressed
                narrated += outcome.narrated
                reused += outcome.reused
                explained += outcome.explained
                explanations_reused += outcome.explanations_reused

        uow.commit()

    result = ArtifactCompileResult(
        definitions_considered=len(definitions),
        nodes_considered=nodes_considered,
        proposals_created=created,
        proposals_revived=revived,
        proposals_abandoned=abandoned,
        unchanged_skipped=skipped,
        proposals_conflicted=conflicted,
        blocks_suppressed=suppressed,
        nodes_failed=nodes_failed,
        blocks_narrated=narrated,
        blocks_narrative_reused=reused,
        blocks_explained=explained,
        blocks_explanation_reused=explanations_reused,
    )
    logger.info(
        "artifact_compile_completed",
        workspace_id=workspace_id,
        definitions_considered=result.definitions_considered,
        nodes_considered=result.nodes_considered,
        proposals_created=result.proposals_created,
        proposals_revived=result.proposals_revived,
        proposals_abandoned=result.proposals_abandoned,
        unchanged_skipped=result.unchanged_skipped,
        proposals_conflicted=result.proposals_conflicted,
        blocks_suppressed=result.blocks_suppressed,
        nodes_failed=result.nodes_failed,
        blocks_narrated=result.blocks_narrated,
        blocks_narrative_reused=result.blocks_narrative_reused,
        blocks_explained=result.blocks_explained,
        blocks_explanation_reused=result.blocks_explanation_reused,
    )
    return result


def _definition_title(
    definition: StoredArtifactDefinition,
    source: EntityCardSource,
) -> str:
    """정의가 만드는 문서의 제목을 짓는다.

    제목은 대상 엔티티의 이름을 그대로 쓴다. 제목은 명사구이고, 문서
    종류를 가리는 일은 응답의 kind 필드가 맡는다. 종류 문자열을 제목
    앞에 덧붙이면 사람이 읽는 이름 자리에 기계용 값이 섞인다.

    LLM이 쓰는 문장형 헤드라인은 summary 블록의 narrative에만 두고
    제목으로는 쓰지 않는다.
    """
    return source.display_name


def _style_instruction(
    uow: DefinitionCompileUnitOfWork,
    definition: StoredArtifactDefinition,
    narrator: BlockNarrator | None,
) -> str:
    """정의가 걸린 채널의 문체를 지시문 한 문단으로 푼다.

    narrator가 없으면 읽지 않는다. 쓰지 않을 값을 위해 정의마다 채널을
    한 번씩 더 조회할 이유가 없다.

    카탈로그에 없는 id는 기본 지시문으로 떨어진다. 문체 상수는 개정되는
    목록이라, 지난 선택이 목록에서 빠졌다고 그 채널의 컴파일이 멈추면
    상수 개정이 파이프라인을 세운다.
    """
    if narrator is None:
        return DEFAULT_STYLE_INSTRUCTION
    style_id = uow.artifact_definitions.find_channel_style(
        channel_id=definition.channel_id,
    )
    if style_id is None:
        return DEFAULT_STYLE_INSTRUCTION
    style = find_style(style_id)
    if style is None:
        return DEFAULT_STYLE_INSTRUCTION
    return style.instruction


def _purpose_sentence(
    uow: DefinitionCompileUnitOfWork,
    definition: StoredArtifactDefinition,
) -> str:
    """채널이 고른 목적과 정의 kind로 문서의 쓰임 한 줄을 만든다.

    사람이 온보딩에서 고른 목적을 먼저 적고 kind 설명을 잇는다. kind는
    목적을 이루는 수단으로 추천된 값일 뿐이라, kind 설명만 실으면 왜 이
    문서를 만들었는지가 프롬프트에서 사라진다.

    채널이 목적을 여러 개 고를 수 있으므로, 그 가운데 이 정의의 kind를
    추천하는 목적만 골라 고른 순서대로 적는다. 다른 kind를 추천하는
    목적까지 적으면 문서 하나가 여러 용도를 주장하게 된다.

    카탈로그는 코드 상수라 포트를 거치지 않고 직접 읽는다. 남는 목적이
    없거나 카탈로그 밖 id뿐이면 kind 한 줄만, 카탈로그 밖 kind면 기본 한
    줄만 남는다. 상수 개정도 손으로 넣은 정의도 컴파일을 멈추지 않는다.

    kind 설명은 그 자체로 끝맺은 한 문장이라 뒤에 용도를 덧붙이지 않는다.
    덧붙이면 한 줄 안에 문장이 둘 겹쳐 읽힌다.
    """
    purpose_ids = uow.artifact_definitions.find_channel_purposes(
        channel_id=definition.channel_id,
    )
    preset_kind = find_kind_by_name(definition.kind)
    kind_sentence = (
        DEFAULT_PURPOSE_SENTENCE
        if preset_kind is None
        else f"이 문서는 {preset_kind.description}"
    )
    labels = []
    for purpose_id in purpose_ids:
        found = find_purpose(purpose_id)
        if found is None:
            continue
        _, purpose = found
        # 이 kind를 추천하는 목적만 이 문서의 목적으로 적는다. 다른 kind의
        # 목적을 함께 적으면 문서 하나가 여러 용도를 주장하게 된다.
        if purpose.recommended_kind == definition.kind:
            labels.append(purpose.label)
    if not labels:
        return kind_sentence
    joined = ", ".join(f"'{label}'" for label in labels)
    return f"이 문서의 목적은 {joined}이다. {kind_sentence}"


def _actor_exposure(
    uow: DefinitionCompileUnitOfWork,
    definition: StoredArtifactDefinition,
) -> str:
    """정의가 걸린 채널의 목적으로 행위자 노출 수준을 정한다.

    노출은 도메인이 정하고 목적은 그 도메인을 가리키는 손잡이다. 목적이
    여럿이어도 같은 도메인이라 첫 목적으로 노출을 정한다. 목적이 없거나
    카탈로그 밖 id면 기본 수준으로 떨어진다. 모르는 목적에 더 넓은 수준을
    주면 이메일이 조용히 문서로 새어 나간다.

    narrator 유무와 무관하게 읽는다. 노출은 산문이 아니라 블록 본문 자체를
    바꾸므로, 서술을 붙이지 않는 컴파일에서도 같은 값이 필요하다.
    """
    purposes = uow.artifact_definitions.find_channel_purposes(
        channel_id=definition.channel_id,
    )
    return find_actor_exposure(purposes[0] if purposes else None)


def _actor_edge_line(exposure: str) -> EdgeFormatter:
    """노출 수준을 박아 둔 간선 서식을 만든다.

    노출은 문서를 읽는 자리에서만 정해지는 값이라 순회가 알 필요가 없다.
    행위자가 아닌 노드는 어느 수준에서도 이름이 그대로다.

    노출을 적용한 이름은 공유 서식에 넘겨 줄을 만든다. 한 줄로 접기와
    빈 이름의 노드 식별자 대체가 노출을 거친 뒤에도 그대로 걸려야 하기
    때문이다.
    """

    def _line(edge: StoredRelationEdge, relation_type: str) -> str:
        return format_edge_line(
            edge,
            relation_type,
            source_name=actor_display(
                edge.source_display_name, edge.source_attributes, exposure
            ),
            target_name=actor_display(
                edge.target_display_name, edge.target_attributes, exposure
            ),
        )

    return _line


def _relation_blocks(
    uow: DefinitionCompileUnitOfWork,
    *,
    definition: StoredArtifactDefinition,
    source: EntityCardSource,
    ontology_version: str | None,
    now: datetime,
    exposure: str,
) -> tuple[ArtifactBlock, ...]:
    """정의가 고른 경로마다 관계 절을 하나씩 만든다.

    차례는 정의에 적힌 경로 차례 그대로다. 어느 관계가 더 중요한지는
    컴파일러가 판단할 일이 아니고, 사람이 적어 둔 차례가 곧 읽는
    차례이기 때문이다.

    이을 것도 잘린 걸음도 없는 경로는 블록을 만들지 않는다. 잘라 낸
    것이 없으면 감춘 것도 없으므로 그 문서는 나머지 절로 그대로 선다.

    본문 줄의 이름은 exposure가 정한 수준으로 적는다. 노출은 블록 본문을
    바꾸므로 산문을 붙이지 않는 컴파일에서도 같이 걸린다.

    잘림만 있고 완주가 없으면 그 문서의 컴파일은 실패한다 — 불완전할
    수 있는 문서를 소비 표면에 올리지 않는다. 근거 장부에는 완주한
    간선만 남으므로 이때 관계 절은 근거가 비어 설 수 없고, 그 절만
    빼고 문서를 올리면 읽는 사람은 잘려 나간 것이 있다는 사실을 알
    길이 없다. 잘림을 알리는 문구를 블록으로 싣는 길도 막혀 있다 —
    근거 없는 블록은 블록 계약이 받지 않고, 읽는 사람에게 보여 줄 것도
    아니다.

    Raises:
        RelationPathTruncatedError: 잘린 걸음이 있는데 완주한 가지가
            없을 때 던진다. 부르는 쪽이 이 문서 하나만 접는다.
    """
    blocks: list[ArtifactBlock] = []
    for index, path in enumerate(definition.selection_spec.relation_paths):
        traversal = traverse_relation_path(
            uow.relations,
            start_node_id=source.node_id,
            path=path,
            now=now,
            edge_line=_actor_edge_line(exposure),
        )
        block = relation_section_block(
            path=path,
            traversal=traversal,
            ontology_version=ontology_version,
        )
        if block is None:
            if traversal.truncated_steps:
                raise RelationPathTruncatedError(
                    path_index=index,
                    truncated_steps=traversal.truncated_steps,
                )
            continue
        blocks.append(block)
    return tuple(blocks)


@dataclass(frozen=True, slots=True)
class _NodeOutcome:
    """노드 하나를 컴파일한 결과의 집계를 담는다.

    Attributes:
        created: 새로 올린 변경안 수를 나타낸다.
        revived: 낡은 계류를 접고 그 자리를 대신한 수를 나타낸다.
        abandoned: 접은 계류 변경안 수를 나타낸다.
        skipped: 지문이 그대로라 아무것도 쓰지 않았는지 나타낸다.
        conflicted: 멱등 키가 결정된 행과 부딪혀 건너뛰었는지 나타낸다.
        suppressed: 반려 장부에 걸려 카드에서 뺀 블록 수를 나타낸다.
        narrated: 새로 산문을 받은 블록 수를 나타낸다.
        reused: 지난 산문을 그대로 다시 쓴 블록 수를 나타낸다.
        explained: 새로 수정 이유를 받은 블록 수를 나타낸다.
        explanations_reused: 지난 수정 이유를 그대로 다시 쓴 블록 수를
            나타낸다.
    """

    created: int = 0
    revived: int = 0
    abandoned: int = 0
    skipped: int = 0
    conflicted: int = 0
    suppressed: int = 0
    narrated: int = 0
    reused: int = 0
    explained: int = 0
    explanations_reused: int = 0


def _propose_node_blocks(
    uow: ArtifactCompileUnitOfWork,
    *,
    workspace_id: int,
    node_id: uuid.UUID,
    artifact_id: uuid.UUID,
    blocks: tuple[ArtifactBlock, ...],
    pending: Sequence[StoredPendingProposal],
    ontology_version: str | None,
    narrator: BlockNarrator | None = None,
    style_instruction: str = DEFAULT_STYLE_INSTRUCTION,
    purpose_sentence: str = DEFAULT_PURPOSE_SENTENCE,
) -> _NodeOutcome:
    """만들어 둔 블록을 반려 장부와 지문을 거쳐 변경안으로 올린다.

    무엇을 싣느냐는 입구가 정하고, 그것을 사람 앞에 어떻게 올리느냐는
    여기가 정한다. 두 입구가 이 자리를 나눠 쓰므로 반려 억제와 지문
    비교와 멱등 키 규칙이 입구마다 갈리지 않는다.

    머리말 블록은 여기서 다시 센다. 머리말은 아래 블록을 집계한 줄이라,
    반려로 빠진 블록이 있는데 옛 집계를 그대로 두면 문서가 싣지 않은
    근거를 가리키게 된다. 다시 센 줄도 반려 장부를 거치므로 사람이
    머리말 자체를 물린 판단은 그대로 살아 있다.

    Raises:
        NarrationError: 블록 산문이나 수정 이유를 받아 오지 못했을 때
            그대로 올라간다. 부르는 쪽이 이 문서 하나만 접는다.
    """
    rejected = uow.block_verdicts.find_rejected_hashes(
        artifact_id=artifact_id,
    )
    summary_ontology_version = next(
        (
            block.ontology_version
            for block in blocks
            if block.block_kind == BLOCK_KIND_SUMMARY
        ),
        None,
    )
    had_summary = any(
        block.block_kind == BLOCK_KIND_SUMMARY for block in blocks
    )
    blocks = tuple(
        block for block in blocks if block.block_kind != BLOCK_KIND_SUMMARY
    )
    blocks, dropped, suppressed_ids = _drop_rejected_blocks(
        blocks,
        rejected,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
    )
    suppressed = dropped
    reopened, dropped_again, _ = _drop_rejected_blocks(
        _revive_suppressed_questions(
            blocks,
            pending=pending,
            suppressed_ids=suppressed_ids,
            ontology_version=ontology_version,
        ),
        rejected,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
    )
    # 되살린 열린 질문도 같은 반려 장부를 거친다. 그 형태까지 사람이
    # 반려했다면 되살릴 것이 아니라 빠져야 한다.
    suppressed += dropped_again
    if reopened:
        validate_blocks(reopened)
        blocks = (*blocks, *reopened)
    if blocks and had_summary:
        rebuilt = _summary_blocks(
            blocks,
            ontology_version=summary_ontology_version,
        )
        if rebuilt:
            kept, dropped_summary, _ = _drop_rejected_blocks(
                rebuilt,
                rejected,
                workspace_id=workspace_id,
                artifact_id=artifact_id,
            )
            suppressed += dropped_summary
            blocks = (*kept, *blocks)
            # 다시 센 머리말도 근거 계약을 거친다. 되살린 열린 질문과 같은
            # 자리다. 여기서 만든 블록은 입구의 검사를 거치지 않았다.
            validate_blocks(blocks)
    if not blocks:
        # 남은 문장이 없으면 빈 카드 규칙과 같이 건너뛴다. 다만 큐에
        # 남은 계류는 접는다. 그 계류가 담은 본문이 바로 방금 반려된
        # 내용이라, 두면 사람이 같은 것을 또 본다.
        abandoned = uow.artifacts.abandon_pending_proposals(
            artifact_id=artifact_id,
        )
        logger.info(
            "artifact_compile_node_all_blocks_suppressed",
            workspace_id=workspace_id,
            node_id=str(node_id),
            artifact_id=str(artifact_id),
            blocks_suppressed=dropped,
        )
        return _NodeOutcome(abandoned=abandoned, suppressed=suppressed)

    content_hash = blocks_content_hash(blocks)
    known = uow.artifacts.find_latest_content_hashes(
        artifact_id=artifact_id,
    )
    if content_hash in known:
        return _NodeOutcome(
            skipped=1,
            abandoned=_abandon_stale_pending(
                uow,
                artifact_id=artifact_id,
                content_hash=content_hash,
            ),
            suppressed=suppressed,
        )

    # 기준 판은 두 자리에서 쓴다. 수정 이유를 다시 쓸 수 있는지 고를 때와
    # 변경안에 기준 판을 적을 때다. 두 자리가 같은 판을 봐야 재사용 규칙과
    # 멱등 키 규칙이 어긋나지 않으므로 한 번만 읽어 나눠 쓴다.
    latest = uow.artifacts.find_latest_revision_id_and_number(
        artifact_id=artifact_id,
    )
    base_revision_id = None if latest is None else latest[0]

    # 지문 비교를 지나 "이번에 새로 올린다"가 정해진 뒤에만 서술한다.
    # 앞에 두면 무변경 재컴파일에서도 LLM이 돈다. 산문이 붙어도 위에서
    # 구한 content_hash는 그대로다. 지문 계산이 산문을 빼고 세므로 다시
    # 계산하지 않는다.
    narrated = 0
    reused = 0
    if narrator is not None:
        reusable = uow.artifacts.list_reusable_narratives(
            artifact_id=artifact_id,
        )
        # 문서 하나의 산문을 한 번에 묻는다. 블록마다 따로 물으면 문체
        # 지시와 문서 목적이 블록 수만큼 되풀이되고, 같은 문서의 블록들이
        # 서로 어긋난 문장을 받을 수도 있다. 머리말 세 블록도 같은 요청에
        # 함께 실린다.
        request, block_indices = _document_narration_request(
            blocks,
            reusable=reusable,
            style_instruction=style_instruction,
            purpose_sentence=purpose_sentence,
        )
        # 물을 것이 없으면 부르지 않는다. 모두 재사용에 걸렸거나 근거가
        # 하나도 없는 문서라, 불러도 빈 응답이 돌아온다.
        empty = request.summary is None and not request.blocks
        narration = None if empty else narrator.narrate_document(request)
        narratives_by_index = (
            {}
            if narration is None
            else {
                index: narration.narratives[block_id]
                for block_id, index in block_indices.items()
                if block_id in narration.narratives
            }
        )
        summary_narrative = None if narration is None else narration.summary
        narrated_blocks: list[ArtifactBlock] = []
        for index, block in enumerate(blocks):
            found = reusable.get(block_content_hash(block))
            if found is not None:
                narrated_blocks.append(replace(block, narrative=found))
                reused += 1
                continue
            text = narratives_by_index.get(index)
            if (
                text is None
                and summary_narrative is not None
                and block.block_kind == BLOCK_KIND_SUMMARY
                and block.heading in SUMMARY_SECTION_KEYS
            ):
                # heading이 SummaryNarrative의 필드 이름과 같은 기계 키라
                # 그대로 골라 담는다.
                text = getattr(summary_narrative, block.heading)
            if text is None:
                narrated_blocks.append(block)
                continue
            narrated_blocks.append(replace(block, narrative=text))
            narrated += 1
        blocks = tuple(narrated_blocks)

    explained = 0
    explanations_reused = 0
    if narrator is not None and base_revision_id is not None:
        blocks, explained, explanations_reused = _explain_changed_blocks(
            uow,
            artifact_id=artifact_id,
            blocks=blocks,
            base_revision_id=base_revision_id,
            narrator=narrator,
            purpose_sentence=purpose_sentence,
        )

    # 기준 판을 저장 직전에 한 번 더 읽어 그사이 발행이 있었는지 본다.
    # 위에서 읽은 기준 판과 저장 사이에는 LLM 호출이 들어 있어 시간이
    # 길게 벌어진다. 그동안 다른 검토자가 계류 변경안을 승인하면 새 판이
    # 나고, 여기서 그대로 저장하면 낡은 기준을 적은 계류가 남는다. 그
    # 계류는 발행이 STALE_BASE_REVISION으로 거부하는데, 다음 컴파일은 그
    # 계류의 지문을 보고 무변경으로 건너뛰면서 그 행을 그대로 두므로
    # 스스로 풀리지 않는다. 어긋남을 본 노드는 저장을 접는 것이 유일한
    # 회복 경로다. 저장하지 않으면 다음 컴파일이 새 기준으로 다시 세운다.
    moved = uow.artifacts.find_latest_revision_id_and_number(
        artifact_id=artifact_id,
    )
    if moved != latest:
        logger.warning(
            "artifact_compile_node_base_moved",
            workspace_id=workspace_id,
            node_id=str(node_id),
            artifact_id=str(artifact_id),
            base_revision_id=None if latest is None else str(latest[0]),
            latest_revision_id=None if moved is None else str(moved[0]),
        )
        # 기존 계류도 접지 않는다. 저장할 것이 없는데 큐만 비우면 사람이
        # 보던 안건이 이유 없이 사라진다.
        return _NodeOutcome(
            conflicted=1,
            suppressed=suppressed,
            narrated=narrated,
            reused=reused,
            explained=explained,
            explanations_reused=explanations_reused,
        )

    replaced = uow.artifacts.abandon_pending_proposals(
        artifact_id=artifact_id,
    )
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
        # 두 가지가 여기로 온다. 하나는 결정된 행과 멱등 키가 부딪히는
        # 경우다. 키에 기준 판이 들어가므로 정상 흐름에서는 나지 않고,
        # 나면 데이터 이상 신호다. 다른 하나는 위의 재확인을 지난 뒤
        # 저장 사이에 다른 검토가 새 판을 낸 경우다. 저장소가 문서 행을
        # 잠그고 기준 판이 최신인지 다시 보므로 그 틈이 여기서 잡힌다.
        # 어느 쪽이든 저장하지 않고 이 노드만 건너뛰며, 나머지 노드의
        # 작업은 그대로 커밋한다. 다음 컴파일이 새 기준 판 위에서 다시
        # 세운다.
        #
        # 바로 위에서 접은 계류는 되돌리지 않는다. 새 판이 끼어든
        # 경우에는 그 계류가 이미 승인으로 끝나 접기가 0건이라 되돌릴
        # 것도 없다.
        logger.warning(
            "artifact_compile_proposal_conflict",
            workspace_id=workspace_id,
            node_id=str(node_id),
            artifact_id=str(artifact_id),
            content_hash=content_hash,
        )
        return _NodeOutcome(
            abandoned=replaced,
            conflicted=1,
            suppressed=suppressed,
            narrated=narrated,
            reused=reused,
            explained=explained,
            explanations_reused=explanations_reused,
        )

    logger.info(
        "artifact_compile_proposed",
        workspace_id=workspace_id,
        node_id=str(node_id),
        artifact_id=str(artifact_id),
        proposal_id=str(proposal_id),
        block_count=len(blocks),
        replaced_pending=replaced,
    )
    return _NodeOutcome(
        created=0 if replaced else 1,
        revived=1 if replaced else 0,
        abandoned=replaced,
        suppressed=suppressed,
        narrated=narrated,
        reused=reused,
        explained=explained,
        explanations_reused=explanations_reused,
    )


def _explain_changed_blocks(
    uow: ArtifactCompileUnitOfWork,
    *,
    artifact_id: uuid.UUID,
    blocks: tuple[ArtifactBlock, ...],
    base_revision_id: uuid.UUID,
    narrator: BlockNarrator,
    purpose_sentence: str,
) -> tuple[tuple[ArtifactBlock, ...], int, int]:
    """발행 판과 짝이 맞으면서 내용이 달라진 블록에 수정 이유를 붙인다.

    짝이 있는 블록만 대상이다. 새로 생긴 절은 비교할 이전 내용이 없고 빠진
    절은 변경안에 자리가 없으므로, 둘 다 물어볼 것이 없다. 화면에 붙는
    문구는 읽는 쪽이 결정론으로 만들어 채운다.

    기준 판이 같은 계류 변경안에 같은 지문의 블록이 있으면 거기 적힌
    문장을 그대로 다시 쓴다. 기준 판이 같으면 짝지을 이전 블록도 같으므로
    다시 물어도 같은 것을 묻는 셈이다.

    Args:
        uow: 문서 저장소를 담은 작업 단위다.
        artifact_id: 이유를 붙일 문서다.
        blocks: 이번에 올릴 블록들이다.
        base_revision_id: 이 변경안이 딛고 선 발행 판이다.
        narrator: 수정 이유를 받아 올 서술기다.
        purpose_sentence: 이 문서가 무엇에 쓰이는지 알리는 한 줄이다.

    Returns:
        이유를 붙인 블록들과, 새로 받은 수, 다시 쓴 수다.

    Raises:
        NarrationError: 수정 이유를 받아 오지 못했을 때 그대로 올라간다.
    """
    base = uow.artifacts.find_latest_revision_blocks(artifact_id=artifact_id)
    if base is None:
        return blocks, 0, 0
    reusable = uow.artifacts.list_reusable_change_reasons(
        artifact_id=artifact_id,
        base_revision_id=base_revision_id,
    )
    explained = 0
    reused = 0
    updated = list(blocks)
    for change in diff_blocks(base, blocks):
        if change.change != CHANGE_MODIFIED:
            continue
        block = updated[change.block_index]
        if block.block_kind == BLOCK_KIND_SUMMARY:
            # 머리말 본문은 아래 블록을 센 값이라 문서 어디가 바뀌어도
            # 함께 바뀐다. 무엇이 달라졌는지는 같은 실행이 새로 쓰는 머리말
            # 산문이 이미 말하므로, 여기서는 수정 이유를 붙이지 않는다.
            # 판정 기준이 block_kind라 머리말 세 블록이 모두 빠진다.
            continue
        found = reusable.get(block_content_hash(block))
        if found is not None:
            updated[change.block_index] = replace(block, change_reason=found)
            reused += 1
            continue
        request = _change_explanation_request(
            block,
            base[change.base_block_index],
            purpose_sentence=purpose_sentence,
        )
        if not request.before_statements and not request.after_statements:
            # 앞뒤 사실 입력이 모두 비면 무엇이 달라졌는지 말할 재료가
            # 없다. 그대로 물으면 프롬프트가 빈 앞면을 "이 블록은 전에
            # 없었다"로 읽어 거짓 전제를 만든다. 이유를 비워 두면 읽는
            # 쪽이 결정론 문구로 채운다.
            continue
        updated[change.block_index] = replace(
            block, change_reason=narrator.explain_change(request)
        )
        explained += 1
    return tuple(updated), explained, reused


def _change_explanation_request(
    block: ArtifactBlock,
    paired: ArtifactBlock,
    *,
    purpose_sentence: str,
) -> ChangeExplanationRequest:
    """짝지어진 두 블록을 수정 이유 요청으로 옮긴다.

    관계 절은 사실 입력이 다르다. 그 블록은 인용을 갖지 않고 본문의 간선
    줄이 곧 사실이므로, 앞뒤를 간선 줄로 만든다. 인용만 읽으면 관계 절의
    앞뒤가 언제나 비어 프롬프트가 빈 앞면을 "이 블록은 전에 없었다"로
    읽는다. 들여쓴 힌트 줄은 관계에 붙은 원문 문장이라 그 말을 한 사람이
    관계의 상대 노드로 읽힐 자리가 있으므로 서술 때와 같이 뺀다.

    나머지 블록의 앞뒤 사실 입력은 검증된 인용뿐이다. 블록 본문과 제목은 색인용 라벨에서
    온 문장이라 근거가 아니고, 검증되지 않은 인용은 아직 근거가 아니다.
    새로 붙은 인용은 뒤에만 있는 문장으로 계산한다. 그것이 이번 변경을
    불러온 것을 말할 수 있는 유일한 재료다.

    Args:
        block: 이번에 올릴 블록이다.
        paired: 발행 판에서 짝지어진 블록이다.
        purpose_sentence: 이 문서가 무엇에 쓰이는지 알리는 한 줄이다.

    Returns:
        수정 이유를 묻는 요청이다.
    """
    if block.block_kind == BLOCK_KIND_RELATION_SECTION:
        before = _relation_edge_lines(paired)
        after = _relation_edge_lines(block)
    else:
        before = _verified_statements(paired)
        after = _verified_statements(block)
    seen = set(before)
    return ChangeExplanationRequest(
        heading=block.heading,
        before_statements=before,
        after_statements=after,
        new_sources=tuple(
            statement for statement in after if statement not in seen
        ),
        purpose_sentence=purpose_sentence,
    )


def _relation_edge_lines(block: ArtifactBlock) -> tuple[str, ...]:
    """관계 절 본문에서 간선 줄만 차례대로 모은다.

    본문은 간선 줄과 들여쓴 힌트 줄이 섞여 있다. 힌트 줄은 관계에 붙은
    원문 문장이라 사실 입력이 아니므로 접두로 갈라 뺀다.
    """
    return tuple(
        line
        for line in block.body.split("\n")
        if line.strip() and not line.startswith(RELATION_HINT_PREFIX)
    )


def _verified_statements(block: ArtifactBlock) -> tuple[str, ...]:
    """블록이 담은 인용 중 대조를 통과한 원문만 차례대로 모은다."""
    return tuple(
        source.statement
        for source in block.sources
        if source.citation_verified
    )


def _document_narration_request(
    blocks: Sequence[ArtifactBlock],
    *,
    reusable: Mapping[str, str],
    style_instruction: str,
    purpose_sentence: str,
) -> tuple[DocumentNarrationRequest, dict[int, int]]:
    """산문이 필요한 블록만 모아 문서 하나의 서술 요청을 만든다.

    지난 산문을 그대로 쓸 수 있는 블록은 요청에 싣지 않는다. 이미 답이
    있는 것을 다시 물으면 값을 치르고 문장이 흔들리기만 한다. 근거가 없어
    서술하지 않는 블록도 싣지 않는다.

    머리말 세 블록은 요청에 따로 서지 않고 summary 한 칸으로 함께 실린다.
    세 블록은 같은 집계 한 줄을 딛고 선 한 벌이라 따로 물으면 서로 어긋난
    문장을 받을 수 있다. summary의 재료는 언제나 첫 머리말 블록으로
    만든다. 세 블록은 heading만 다르고 본문과 근거가 같아 어느 블록으로
    만들어도 사실 입력은 같지만, 만드는 자리를 못박아야 재사용이 어느
    블록에서 걸리든 같은 재료가 나간다. 세 블록이 모두 재사용에 걸리면
    summary는 None이다.

    Args:
        blocks: 이번 판에 실릴 블록을 차례대로 받는다.
        reusable: 블록 내용 지문을 지난 산문에 짝지은 사전을 받는다.
        style_instruction: 문서 전체에 한 번 실을 문체 지시를 받는다.
        purpose_sentence: 문서 전체에 한 번 실을 목적 문장을 받는다.

    Returns:
        서술 요청과, 요청 안의 블록 번호를 blocks 안의 자리 번호로 잇는
        사전을 함께 돌려준다. 응답이 블록 번호로 오므로 그 산문을 다시
        블록에 얹으려면 이 사전이 필요하다.
    """
    summary_input: BlockNarrationInput | None = None
    summary_wanted = False
    section_inputs: list[BlockNarrationInput] = []
    indices: dict[int, int] = {}
    for index, block in enumerate(blocks):
        is_reusable = block_content_hash(block) in reusable
        if block.block_kind == BLOCK_KIND_SUMMARY:
            if summary_input is None:
                summary_input = _block_narration_input(
                    block, block_id=_SUMMARY_BLOCK_ID
                )
            if not is_reusable and block.heading in SUMMARY_SECTION_KEYS:
                summary_wanted = True
            continue
        if is_reusable:
            continue
        block_input = _block_narration_input(
            block, block_id=len(section_inputs)
        )
        if block_input is None:
            continue
        indices[block_input.block_id] = index
        section_inputs.append(block_input)
    return (
        DocumentNarrationRequest(
            style_instruction=style_instruction,
            purpose_sentence=purpose_sentence,
            summary=summary_input if summary_wanted else None,
            blocks=tuple(section_inputs),
        ),
        indices,
    )


def _block_narration_input(
    block: ArtifactBlock,
    *,
    block_id: int,
) -> BlockNarrationInput | None:
    """블록 하나를 서술 재료로 옮긴다. 근거가 없으면 None이다.

    관계 절은 사실 입력이 다르다. 그 블록은 인용을 갖지 않고 근거를
    관계 장부로 남기며, 본문 줄이 곧 사실 입력이다. 그래서 관계 절만 본문
    줄을 넘기고, 검증된 인용을 요구하는 규칙은 나머지 블록에만 건다.

    다만 본문 줄을 통째로 사실로 넘기지는 않는다. 들여쓴 힌트 줄은 관계에
    붙은 원문 문장이라 그 말을 한 사람이 관계의 상대 노드로 읽힐 자리가
    있다. 그래서 접두로 갈라 간선 줄만 사실로 넘기고 원문 문장은 표현
    힌트로 넘긴다. 잘린 걸음을 알리는 줄은 사실이므로 간선 쪽에 남는다.

    claim 절·열린 질문·대조·머리말 블록의 사실 입력은 검증된 인용뿐이다.
    블록 본문과 제목은 색인용 라벨에서 온 문장이라 근거가 아니라 주제
    힌트로만 넘긴다. 머리말 블록은 본문이 결정론 집계 한 줄이므로 그 줄이
    그대로 주제 힌트가 되고, 사실 입력은 문서 전체의 검증된 인용이다.

    대조 블록은 자기 sources를 비우고 근거를 후보마다 나눠 갖는다. 후보를
    합치면 어느 인용이 어느 값의 근거인지 사라지므로 갈라서 넘긴다. 검증된
    인용이 하나도 없는 후보는 아예 뺀다. 프롬프트는 후보 본문을 사실로
    싣고 모든 후보를 서술하라고 시키므로, 근거 없는 후보를 남기면 검증되지
    않은 값이 사실로 나간다.

    검증된 인용이 하나도 없으면 서술하지 않는다. 근거 없는 문장을 만들지
    않는 것이지 오류가 아니므로 예외가 아니라 None으로 알린다.

    Args:
        block: 재료로 옮길 블록을 받는다.
        block_id: 요청 안에서 이 블록을 가리킬 번호를 받는다. 응답이 이
            번호로 오므로 부르는 쪽이 정해서 준다.
    """
    if block.block_kind == BLOCK_KIND_RELATION_SECTION:
        edges = _relation_edge_lines(block)
        hints = tuple(
            line[len(RELATION_HINT_PREFIX) :]
            for line in block.body.split("\n")
            if line.startswith(RELATION_HINT_PREFIX)
        )
        if not edges and not hints:
            return None
        return BlockNarrationInput(
            block_id=block_id,
            block_kind=block.block_kind,
            heading=block.heading,
            topic_hint=block.heading,
            statements=(),
            edges=edges,
            hints=hints,
            variants=(),
        )
    statements = _verified_statements(block)
    variants = tuple(
        (body, verified)
        for body, verified in (
            (
                variant.body,
                tuple(
                    source.statement
                    for source in variant.sources
                    if source.citation_verified
                ),
            )
            for variant in block.variants
        )
        if verified
    )
    if not statements and not variants:
        return None
    return BlockNarrationInput(
        block_id=block_id,
        block_kind=block.block_kind,
        heading=block.heading,
        topic_hint=block.body,
        statements=statements,
        edges=(),
        hints=(),
        variants=variants,
    )


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
    return uow.artifacts.abandon_pending_proposals(
        artifact_id=artifact_id,
        except_content_hash=content_hash,
    )


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
    allowed: tuple[str, ...] | None = None,
    relation_blocks: tuple[ArtifactBlock, ...] = (),
) -> tuple[ArtifactBlock, ...]:
    """카드 본문을 이룰 블록을 정해진 순서로 만든다.

    대조로 실린 모순 안건은 열린 질문에서 뺀다. 같은 안건이 카드에 두 번
    나오면 검토자가 한 결정을 두 자리에서 내려야 하기 때문이다.

    관계 절은 claim 절과 열린 질문 사이에 놓는다. 앞쪽은 이 대상이
    무엇인지를, 뒤쪽은 사람에게 묻는 것을 말하므로, 대상과 이웃의
    관계는 그 사이에 온다.

    실을 내용이 있으면 머리말 블록 셋을 맨 앞에 세운다. 문서를 열자마자
    읽는 자리라 아래 블록들을 집계한 한 줄이 먼저 와야 한다.
    """
    ontology_version = vocabulary.snapshot_id or None
    sections = _claim_sections(
        claims,
        vocabulary,
        ontology_version,
        now,
        _contradictions(pending),
        allowed=allowed,
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
    body = tuple([*sections, *relation_blocks, *questions])
    return (
        *_summary_blocks(body, ontology_version=ontology_version),
        *body,
    )


# 머리말 블록이 나르는 근거 인용의 상한이다. 근거 수를 제한하는 것은 산문
# 입력 길이를 묶기 위해서다. 넘치면 최근 것부터 남긴다.
_SUMMARY_SOURCE_LIMIT = 40


def _summary_blocks(
    blocks: Sequence[ArtifactBlock],
    *,
    ontology_version: str | None,
) -> tuple[ArtifactBlock, ...]:
    """문서 맨 앞에 세울 머리말 블록 셋을 만든다. 근거가 없으면 빈 튜플이다.

    머리말은 한 줄 요약·원하는 결과·요청 배경 세 섹션이다. 세 섹션은
    본문의 다른 섹션과 같은 급의 최상위 섹션이므로 각각 블록 하나로
    선다. 블록이 곧 검수 단위라, 셋을 한 블록에 묶으면 검토자가 세 섹션을
    한 번에만 승인하거나 반려할 수 있다.

    세 블록의 heading은 SUMMARY_SECTION_KEYS의 기계 키를 그대로 쓰고,
    화면에 보여 줄 한글 제목은 읽기 레이아웃이 붙인다.

    본문은 아래 블록들을 센 집계 한 줄이고, 세 블록에 같은 줄을 싣는다.
    이 집계가 세 섹션이 함께 딛고 선 결정론 내용이고, 내용 지문이 같은
    기준으로 움직여야 문서가 바뀔 때 세 섹션이 함께 다시 서술되기
    때문이다. heading이 서로 달라 세 블록의 지문은 각각 다르다.

    LLM을 부르지 않고 세기만 하므로 같은 입력이면 같은 줄이 나온다. 집계
    항목의 순서와 표기를 바꾸면 내용 지문이 달라져 사람이 이미 본 카드가
    검토 큐에 다시 쌓이므로, 형식은 시험으로 고정한다.

    claim 장부와 근거는 모든 블록의 합집합이다. 머리말이 문서 전체를
    가리키는 블록이기 때문이다. 합칠 때는 정렬해 순서를 고정한다. 블록이
    들어온 차례나 저장소가 돌려준 차례에 기대면 같은 입력이 다른 지문을
    낳는다.

    claim 근거가 하나도 없으면 만들지 않는다. 관계만 있는 문서가 그런
    경우인데, 머리말은 claim 장부를 요구하는 블록이라 빈 장부로 세우면
    근거 계약에 걸린다.

    근거가 상한을 넘으면 최근 것부터 남긴다. 머리말 산문은 이 문서가 지금
    어떤 상태인지를 말해야 하는데, 오래된 쪽을 남기면 본문이 적은 최근
    보고 시각과 산문이 읽은 근거가 어긋난다. 본문의 최초·최근 보고
    시각은 자르기 전 근거 전체에서 센다.
    """
    if not blocks:
        return ()
    claim_ids = sorted(
        {claim_id for block in blocks for claim_id in block.claim_ids},
        key=str,
    )
    if not claim_ids:
        return ()
    relation_count = len(
        {
            relation_id
            for block in blocks
            for relation_id in block.relation_ids
        }
    )
    question_count = sum(
        1
        for block in blocks
        if block.block_kind == BLOCK_KIND_OPEN_QUESTION
    )
    sources = sorted(
        {source for block in blocks for source in block.sources},
        key=lambda source: (
            source.observed_at,
            str(source.claim_id),
            source.statement,
        ),
    )
    if sources:
        first = sources[0].observed_at.isoformat()
        last = sources[-1].observed_at.isoformat()
    else:
        first = "없음"
        last = "없음"
    body = (
        f"claim {len(claim_ids)}건"
        f" · 관계 {relation_count}건"
        f" · 열린 질문 {question_count}건"
        f" · 최초 보고 {first}"
        f" · 최근 보고 {last}"
    )
    return tuple(
        ArtifactBlock(
            block_kind=BLOCK_KIND_SUMMARY,
            heading=section_key,
            body=body,
            claim_ids=tuple(claim_ids),
            proposal_ids=(),
            ontology_version=ontology_version,
            sources=tuple(sources[-_SUMMARY_SOURCE_LIMIT:]),
        )
        for section_key in SUMMARY_SECTION_KEYS
    )


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
    *,
    allowed: tuple[str, ...] | None = None,
) -> list[ArtifactBlock]:
    """predicate별 claim_section 블록을 정해진 순서대로 만든다.

    고른 절(allowed)이 없으면 사전 순서를 따른다. 사전에 등재된
    predicate가 사전이 정의한 순서로 먼저 오고, 미등재 predicate가
    이름순으로 뒤를 잇는다. 사전 순서는 사람이 정한 읽는 순서이므로
    그것이 카드의 순서가 된다. 미등재를 이름순으로 두는 것은 기댈
    순서가 이름밖에 없기 때문이다.

    고른 절이 있으면 그 이름들만 그 차례로 싣는다. 정의가 적어 둔
    차례가 곧 사람이 읽겠다고 정한 차례이므로 사전 순서보다 앞선다.
    빈 목록은 "하나도 고르지 않음"이라 claim 절이 없는 문서가 된다 —
    고르지 않음(None)과 뜻이 다르므로 같이 다루지 않는다.

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

    if allowed is None:
        order = {
            entry.name: index
            for index, entry in enumerate(vocabulary.predicate_entries)
        }
    else:
        order = {name: index for index, name in enumerate(allowed)}
        grouped = {
            predicate: members
            for predicate, members in grouped.items()
            if predicate in order
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
