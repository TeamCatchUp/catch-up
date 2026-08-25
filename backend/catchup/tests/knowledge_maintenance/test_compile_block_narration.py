"""컴파일이 언제 산문을 부르고 언제 부르지 않는지 fake로 확인한다.

호출 횟수가 곧 규칙이다. 무변경 재컴파일에 LLM이 돌면 검토 큐가 흔들리기
전에 비용부터 새고, 한 블록만 바뀐 재컴파일에 문서 전체가 다시 쓰이면
검수자가 진짜 변화를 못 찾는다.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from structlog.testing import capture_logs

from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.preset_catalog import DEFAULT_PURPOSE_SENTENCE
from catchup.knowledge_maintenance.domain.preset_catalog import (
    DEFAULT_STYLE_INSTRUCTION,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredPendingProposal
from catchup.knowledge_maintenance.ports.narrator import ChangeExplanationRequest
from catchup.knowledge_maintenance.ports.narrator import DocumentNarration
from catchup.knowledge_maintenance.ports.narrator import DocumentNarrationRequest
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.knowledge_maintenance.ports.narrator import SummaryNarrative
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    _actor_edge_line,
)
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_definition_artifacts,
)
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import (
    VOCABULARY,
)
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import (
    WORKSPACE,
)
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import (
    FakeDefinitionUnitOfWork,
)
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import (
    FakeRelationRepository,
)
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import _claim
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import (
    _definition_row,
)
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import _spec


def _content_headings(narrator) -> list[str]:
    """요청에 실린 본문 블록의 제목만 모은다.

    머리말은 요청의 summary 칸으로 따로 실리므로 여기에 섞이지 않는다.
    어느 절이 다시 서술됐는지 보는 시험에서 쓴다.
    """
    return [
        block.heading
        for request in narrator.requests
        for block in request.blocks
    ]


def _summary_requests(narrator) -> list[DocumentNarrationRequest]:
    """머리말 재료를 실은 요청만 모은다."""
    return [
        request for request in narrator.requests if request.summary is not None
    ]


def _block_input(narrator, block_kind: str):
    """요청에 실린 블록 재료 가운데 주어진 종류 하나를 꺼낸다."""
    return next(
        block
        for request in narrator.requests
        for block in request.blocks
        if block.block_kind == block_kind
    )


def _relation_request(narrator):
    """요청에 실린 블록 재료 가운데 관계 절 것 하나를 꺼낸다."""
    return _block_input(narrator, BLOCK_KIND_RELATION_SECTION)


class _FakeNarrator:
    """호출을 기록하고 고정 문장을 돌려주는 서술기다.

    문서 산문 요청과 수정 이유 요청을 따로 담는다. 두 요청은 부르는
    조건이 다르므로 한 목록에 섞으면 어느 규칙이 깨졌는지 가릴 수 없다.

    requests의 길이가 곧 narrate_document 호출 수다. 한 노드가 문서를
    한 번만 묻는지 이 길이로 본다.
    """

    def __init__(
        self,
        error: Exception | None = None,
        *,
        explain_error: Exception | None = None,
    ) -> None:
        self.requests: list[DocumentNarrationRequest] = []
        self.explanations: list[ChangeExplanationRequest] = []
        self.error = error
        self.explain_error = explain_error

    def narrate_document(
        self, request: DocumentNarrationRequest
    ) -> DocumentNarration:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        summary = (
            None
            if request.summary is None
            else SummaryNarrative(
                one_line_summary="A사가 CSV 내보내기를 원한다.",
                desired_outcome="내려받은 파일을 바로 쓸 수 있게 된다.",
                background="지금은 손으로 옮겨 적고 있다.",
            )
        )
        return DocumentNarration(
            summary=summary,
            narratives={
                block.block_id: f"{block.heading} 절을 설명하는 문장이다."
                for block in request.blocks
            },
        )

    def explain_change(self, request: ChangeExplanationRequest) -> str:
        self.explanations.append(request)
        if self.explain_error is not None:
            raise self.explain_error
        return f"{request.heading} 블록이 바뀐 이유다."


def _verified(claim: StoredClaimCandidate) -> StoredClaimCandidate:
    """인용 대조를 통과한 claim으로 바꾼다.

    `_claim` 헬퍼의 기본값은 대조 판정 없음(None)이라 그대로 쓰면 블록에
    검증된 인용이 하나도 없어 서술 대상이 되지 않는다. 서술 규칙을 보는
    시험이므로 여기서 판정을 참으로 세운다.
    """
    return replace(claim, citation_verified=True)


def _uow(
    *,
    claims,
    nodes,
    styles=None,
    sections=("status",),
    kind=None,
    purpose=None,
    purposes=None,
) -> FakeDefinitionUnitOfWork:
    """정의 하나·노드·claim으로 fake UnitOfWork를 세운다."""
    row_kwargs = {} if kind is None else {"kind": kind}
    definition = _definition_row(
        spec=_spec(predicate_sections=list(sections)), **row_kwargs
    )
    uow = FakeDefinitionUnitOfWork(
        definitions=[definition], nodes=nodes, claims=claims
    )
    if styles:
        uow.artifact_definitions.channel_styles = {
            definition[1]: styles,
        }
    chosen = purposes if purposes is not None else ()
    if purpose:
        chosen = (purpose, *chosen)
    if chosen:
        uow.artifact_definitions.channel_purposes = {
            definition[1]: tuple(chosen),
        }
    return uow


def _contradiction(
    *,
    node_id: uuid.UUID,
    claims: tuple[StoredClaimCandidate, ...],
) -> StoredPendingProposal:
    """claim들이 한 predicate에서 갈렸다는 계류 안건을 만든다."""
    return StoredPendingProposal(
        id=uuid.uuid4(),
        proposal_kind="contradiction",
        summary=f"'status' 값이 {len(claims)}종으로 갈린다",
        resolver_metadata={
            "subject_key": f"node:{node_id}",
            "predicate": "status",
            "values": [
                {
                    "claim_id": str(claim.id),
                    "value": claim.value,
                    "normalized": str(claim.value),
                    "observed_at": claim.observed_at.isoformat(),
                    "statement": claim.statement,
                }
                for claim in claims
            ],
        },
    )


def _run(uow, narrator=None):
    """정의 순회 컴파일을 한 번 돌린다."""
    return compile_definition_artifacts(
        uow,
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        narrator=narrator,
    )


def _pending(uow):
    """계류 변경안 행 하나를 꺼낸다."""
    rows = [row for row in uow.artifacts.pending_rows()]
    assert len(rows) == 1
    return rows[0]


def _blocks(uow):
    """계류 변경안 하나의 블록을 꺼낸다."""
    return _pending(uow)["blocks"]


def test_case_a_no_narrator_keeps_the_old_result() -> None:
    """narrator가 없으면 블록에 손대지 않는다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )

    result = _run(uow)

    assert result.blocks_narrated == 0
    assert result.blocks_narrative_reused == 0
    assert all(block.narrative is None for block in _blocks(uow))


def test_case_b_first_compile_narrates_every_block() -> None:
    """첫 컴파일은 서술 가능한 블록을 한 번의 호출로 모두 채운다.

    요청에 실리는 블록 수는 서술 대상보다 셋 적다. 머리말 세 블록은
    blocks가 아니라 summary 한 칸으로 실리기 때문이다.
    """
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )
    narrator = _FakeNarrator()

    result = _run(uow, narrator)

    blocks = _blocks(uow)
    narratable = [block for block in blocks if block.sources]
    assert len(narrator.requests) == 1
    assert narrator.requests[0].summary is not None
    assert len(narrator.requests[0].blocks) == len(narratable) - 3
    assert result.blocks_narrated == len(narratable)
    assert all(block.narrative for block in narratable)


def test_one_node_asks_the_document_exactly_once() -> None:
    """절이 여럿이어도 노드 하나가 문서를 묻는 것은 한 번뿐이다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[
            _verified(_claim(node_id=node_id, predicate="status")),
            _verified(
                _claim(node_id=node_id, predicate="priority", value="높음")
            ),
        ],
        sections=("status", "priority"),
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    assert len(narrator.requests) == 1
    assert sorted(_content_headings(narrator)) == ["priority", "status"]


def test_summary_sections_are_three_blocks_narrated_by_one_call() -> None:
    """머리말 세 블록이 맨 앞에 서고 한 번의 서술로 함께 채워진다.

    세 섹션은 본문의 다른 섹션과 같은 급이라 각각 블록 하나로 선다.
    heading은 기계 키이고, 재료는 요청의 summary 한 칸으로만 실린다.
    """
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    blocks = _blocks(uow)
    summaries = blocks[:3]
    assert [block.block_kind for block in summaries] == [
        BLOCK_KIND_SUMMARY
    ] * 3
    assert [block.heading for block in summaries] == [
        "one_line_summary",
        "desired_outcome",
        "background",
    ]
    assert [block.narrative for block in summaries] == [
        "A사가 CSV 내보내기를 원한다.",
        "내려받은 파일을 바로 쓸 수 있게 된다.",
        "지금은 손으로 옮겨 적고 있다.",
    ]
    assert len(narrator.requests) == 1
    summary_requests = _summary_requests(narrator)
    assert len(summary_requests) == 1
    assert summary_requests[0].summary.heading == "one_line_summary"
    # 본문은 세 블록 모두 같은 집계 한 줄이고, heading이 달라 지문은
    # 서로 다르다.
    assert len({block.body for block in summaries}) == 1
    assert len({block_content_hash(block) for block in summaries}) == 3


def test_summary_blocks_are_not_narrated_without_a_narrator() -> None:
    """서술기를 주지 않으면 머리말 세 블록 모두 산문이 없다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )

    _run(uow)

    assert all(block.narrative is None for block in _blocks(uow)[:3])


def test_partly_reused_summary_asks_the_summary_once() -> None:
    """세 칸 중 하나만 캐시에 걸려도 머리말은 한 번만 묻고 나머지를 채운다.

    지난 판에 남은 문장은 그대로 살아 있어야 하고, 빠진 칸만 새로 받는다.
    머리말 세 블록은 본문이 같아도 heading이 달라 지문이 각각이므로,
    재사용이 한 칸에만 걸리는 일이 실제로 일어난다.
    """
    node_id = uuid.uuid4()
    claim = _verified(_claim(node_id=node_id))
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[claim],
    )
    narrator = _FakeNarrator()
    _run(uow, narrator)
    first = _pending(uow)
    uow.artifacts.mark_approved(proposal_id=first["id"], reviewer="사람")
    # 발행판에는 첫 머리말 블록의 문장만 남긴다. 나머지 두 칸은 산문이
    # 없어 재사용 사전에 들어가지 않는다.
    uow.artifacts.add_revision(
        artifact_id=first["artifact_id"],
        revision_number=1,
        blocks=[
            replace(block, narrative="지난 판의 한 줄 요약이다.")
            if index == 0
            else replace(block, narrative=None)
            for index, block in enumerate(first["blocks"])
        ],
        source_proposal_id=first["id"],
    )
    # claim 절의 값만 바꾼다. 인용 원문과 관찰 시각은 그대로라 머리말
    # 세 블록의 지문은 움직이지 않고, 본문 절만 새 내용이 된다.
    uow.knowledge_candidates.claims = [replace(claim, value="진행 중")]
    narrator.requests.clear()

    result = _run(uow, narrator)

    summaries = _blocks(uow)[:3]
    assert summaries[0].narrative == "지난 판의 한 줄 요약이다."
    assert summaries[1].narrative == "내려받은 파일을 바로 쓸 수 있게 된다."
    assert summaries[2].narrative == "지금은 손으로 옮겨 적고 있다."
    assert len(narrator.requests) == 1
    assert len(_summary_requests(narrator)) == 1
    assert result.blocks_narrative_reused == 1


def test_case_0_block_without_verified_statement_is_not_narrated() -> None:
    """검증된 인용이 없는 블록은 부르지 않고 실패로 세지도 않는다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[replace(_claim(node_id=node_id), citation_verified=False)],
    )

    result = _run(uow, _FakeNarrator())

    assert result.nodes_failed == 0
    assert result.blocks_narrated == 0
    assert all(block.narrative is None for block in _blocks(uow))


def test_case_c_unchanged_recompile_calls_nothing() -> None:
    """내용이 그대로면 LLM을 한 번도 부르지 않는다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )
    narrator = _FakeNarrator()
    _run(uow, narrator)
    before = len(narrator.requests)

    result = _run(uow, narrator)

    assert result.unchanged_skipped == 1
    assert len(narrator.requests) == before


def test_case_d_changed_block_reuses_the_rest() -> None:
    """한 블록만 바뀌면 그 블록만 새로 쓰고 나머지는 재사용한다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[
            _verified(_claim(node_id=node_id, predicate="status")),
            _verified(
                _claim(node_id=node_id, predicate="priority", value="높음")
            ),
        ],
        sections=("status", "priority"),
    )
    narrator = _FakeNarrator()
    _run(uow, narrator)
    narrator.requests.clear()
    uow.knowledge_candidates.claims.append(
        _verified(
            _claim(
                node_id=node_id,
                predicate="priority",
                value="낮음",
                minutes=5,
            )
        )
    )

    result = _run(uow, narrator)

    # 머리말은 집계가 달라졌으므로 세 블록 모두 다시 서술된다.
    assert len(narrator.requests) == 1
    assert _content_headings(narrator) == ["priority"]
    assert narrator.requests[0].summary is not None
    assert result.blocks_narrated == 4
    assert result.blocks_narrative_reused == 1


def test_pending_narrative_wins_over_the_published_one() -> None:
    """같은 지문이 판과 계류에 다 있으면 계류의 산문을 쓴다.

    계류가 판보다 나중의 문장이다. 판의 문장을 앞세우면 방금 다시 쓴
    산문이 다음 컴파일에서 옛 문장으로 되돌아간다.
    """
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[
            _verified(_claim(node_id=node_id, predicate="status")),
            _verified(
                _claim(node_id=node_id, predicate="priority", value="높음")
            ),
        ],
        sections=("status", "priority"),
    )
    narrator = _FakeNarrator()
    _run(uow, narrator)
    first = _pending(uow)
    uow.artifacts.mark_approved(proposal_id=first["id"], reviewer="사람")
    uow.artifacts.add_revision(
        artifact_id=first["artifact_id"],
        revision_number=1,
        blocks=[
            replace(block, narrative="판에 실린 문장이다.")
            for block in first["blocks"]
        ],
        source_proposal_id=first["id"],
    )
    uow.knowledge_candidates.claims.append(
        _verified(
            _claim(
                node_id=node_id,
                predicate="priority",
                value="낮음",
                minutes=5,
            )
        )
    )
    _run(uow, narrator)
    second = _pending(uow)
    second["blocks"] = tuple(
        replace(block, narrative="계류에 실린 문장이다.")
        for block in second["blocks"]
    )
    uow.knowledge_candidates.claims.append(
        _verified(
            _claim(
                node_id=node_id,
                predicate="priority",
                value="중간",
                minutes=9,
            )
        )
    )

    _run(uow, narrator)

    status_block = next(
        block for block in _blocks(uow) if block.heading == "status"
    )
    assert status_block.narrative == "계류에 실린 문장이다."


def test_case_e_rejected_block_narrative_is_not_reused() -> None:
    """반려된 변경안의 산문은 재사용 사전에 들어가지 않는다.

    지문이 그대로인 블록으로 봐야 이 규칙이 걸린다. 내용까지 바뀌면
    지문이 달라져 어차피 재사용이 빗나가므로, 반려된 산문이 새는지
    마는지가 결과에 드러나지 않는다. 그래서 절 하나만 바꾸고 나머지
    절의 지문은 그대로 둔 채 다시 컴파일한다. 그 절의 산문은 반려된
    행에만 남아 있다.
    """
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[
            _verified(_claim(node_id=node_id, predicate="status")),
            _verified(
                _claim(node_id=node_id, predicate="priority", value="높음")
            ),
        ],
        sections=("status", "priority"),
    )
    narrator = _FakeNarrator()
    _run(uow, narrator)
    uow.artifacts.mark_rejected(
        proposal_id=_pending(uow)["id"],
        reviewer="사람",
        reason="문장이 틀렸다",
    )
    narrator.requests.clear()
    uow.knowledge_candidates.claims.append(
        _verified(
            _claim(
                node_id=node_id,
                predicate="priority",
                value="낮음",
                minutes=5,
            )
        )
    )

    result = _run(uow, narrator)

    assert len(narrator.requests) == 1
    assert sorted(_content_headings(narrator)) == [
        "priority",
        "status",
    ]
    # 머리말 세 블록까지 다섯 블록이 다시 서술된다.
    assert result.blocks_narrated == 5
    assert result.blocks_narrative_reused == 0


def test_case_f_narration_error_fails_the_node() -> None:
    """서술이 실패하면 그 노드는 접히고 제안이 서지 않는다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )

    with capture_logs() as logs:
        result = _run(uow, _FakeNarrator(NarrationError("못 썼다")))

    assert result.nodes_failed == 1
    assert result.proposals_created == 0
    assert uow.artifacts.pending_rows() == []
    assert "artifact_compile_node_failed_narration" in [
        entry["event"] for entry in logs
    ]


def test_narration_error_abandons_the_earlier_pending() -> None:
    """실패 노드의 지난 계류 변경안은 함께 접힌다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )
    _run(uow, _FakeNarrator())
    uow.knowledge_candidates.claims.append(
        _verified(_claim(node_id=node_id, value="배포됨", minutes=10))
    )

    result = _run(uow, _FakeNarrator(NarrationError("못 썼다")))

    assert result.nodes_failed == 1
    assert result.proposals_abandoned == 1
    assert uow.artifacts.pending_rows() == []


def test_case_g_relation_section_is_narrated_from_body_lines() -> None:
    """관계 절은 인용이 없어도 본문 줄을 사실 입력으로 서술한다."""
    node_id = uuid.uuid4()
    target = uuid.uuid4()
    uow = FakeDefinitionUnitOfWork(
        definitions=[
            _definition_row(
                spec=_spec(
                    relation_paths=[
                        {"steps": [{"type": "owned_by", "dir": "out"}]}
                    ],
                    predicate_sections=["status"],
                )
            )
        ],
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
        relations=FakeRelationRepository(
            [
                (
                    "owned_by",
                    StoredRelationEdge(
                        id=uuid.uuid4(),
                        source_node_id=node_id,
                        target_node_id=target,
                        assertion_text="요청 A는 결제팀이 맡는다",
                        source_display_name="요청 A",
                        target_display_name="결제팀",
                    ),
                )
            ]
        ),
    )
    narrator = _FakeNarrator()

    result = _run(uow, narrator)

    relation_input = _relation_request(narrator)
    assert relation_input.statements == ()
    assert relation_input.edges == ("요청 A → owned_by → 결제팀",)
    assert relation_input.hints == ("요청 A는 결제팀이 맡는다",)
    # claim 절·관계 절과 머리말 세 블록이 서술된다.
    assert result.blocks_narrated == 5
    relation_block = next(
        block
        for block in _blocks(uow)
        if block.block_kind == BLOCK_KIND_RELATION_SECTION
    )
    assert relation_block.narrative


def test_style_and_purpose_fall_back_to_the_defaults() -> None:
    """채널 문체도 카탈로그 kind도 없으면 기본 문장을 쓴다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    assert narrator.requests[0].style_instruction == (
        DEFAULT_STYLE_INSTRUCTION
    )
    assert narrator.requests[0].purpose_sentence == DEFAULT_PURPOSE_SENTENCE


def test_channel_style_reaches_the_request() -> None:
    """채널에 걸린 문체가 요청의 지시문으로 풀린다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
        styles="style.support_guide",
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    assert "해요체" in narrator.requests[0].style_instruction


def test_channel_purpose_reaches_the_request() -> None:
    """채널이 고른 목적 이름이 kind 설명과 함께 목적 문장에 실린다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
        kind="feature_request_status",
        purpose="voc.request_status_tracking",
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    assert narrator.requests[0].purpose_sentence == (
        "이 문서의 목적은 '요구 처리 현황 따라가기'이다."
        " 이 문서는 고객이 원하는 기능과 그 이유, 사용 상황을 하나의"
        " 문서로 모은다. 제목은 기능 명칭이 아니라 원하는 결과 중심이다."
    )


def test_same_kind_with_different_purposes_gets_different_sentences() -> None:
    """kind가 같아도 채널이 고른 목적이 다르면 목적 문장이 갈린다."""
    sentences = []
    for purpose in ("voc.top_requests", "voc.request_status_tracking"):
        node_id = uuid.uuid4()
        uow = _uow(
            nodes=[(node_id, "요청 A", "feature_request", "active")],
            claims=[_verified(_claim(node_id=node_id))],
            kind="feature_request_status",
            purpose=purpose,
        )
        narrator = _FakeNarrator()
        _run(uow, narrator)
        sentences.append(narrator.requests[0].purpose_sentence)

    assert sentences[0] != sentences[1]
    assert "많이 들어온 요구 보기" in sentences[0]
    assert "요구 처리 현황 따라가기" in sentences[1]


def test_purpose_sentence_keeps_only_purposes_recommending_this_kind() -> None:
    """목적이 여럿이어도 이 kind를 추천하는 목적만 목적 문장에 실린다.

    다른 kind를 추천하는 목적까지 적으면 문서 하나가 여러 용도를 주장한다.
    """
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
        kind="feature_request_status",
        purposes=("voc.top_requests", "voc.complaint_patterns"),
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    sentence = narrator.requests[0].purpose_sentence
    assert "많이 들어온 요구 보기" in sentence
    assert "반복되는 불편 찾기" not in sentence
    assert "원하는 결과 중심이다." in sentence


def test_purpose_sentence_lists_several_purposes_of_this_kind() -> None:
    """같은 kind를 추천하는 목적이 여럿이면 고른 순서대로 함께 적는다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
        kind="feature_request_status",
        purposes=("voc.top_requests", "voc.request_status_tracking"),
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    assert narrator.requests[0].purpose_sentence.startswith(
        "이 문서의 목적은 '많이 들어온 요구 보기',"
        " '요구 처리 현황 따라가기'이다."
    )


def test_purpose_off_the_recommended_kind_leaves_the_kind_sentence() -> None:
    """고른 목적이 모두 다른 kind를 추천하면 kind 설명 한 줄만 남는다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
        kind="feature_request_status",
        purpose="voc.complaint_patterns",
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    assert narrator.requests[0].purpose_sentence == (
        "이 문서는 고객이 원하는 기능과 그 이유, 사용 상황을 하나의"
        " 문서로 모은다. 제목은 기능 명칭이 아니라 원하는 결과 중심이다."
    )


def test_kind_only_sentence_when_the_channel_has_no_purpose() -> None:
    """목적을 고르지 않은 채널은 kind 설명 한 줄만 쓴다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
        kind="feature_request_status",
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    assert narrator.requests[0].purpose_sentence == (
        "이 문서는 고객이 원하는 기능과 그 이유, 사용 상황을 하나의"
        " 문서로 모은다. 제목은 기능 명칭이 아니라 원하는 결과 중심이다."
    )


def test_request_carries_only_verified_statements() -> None:
    """검증 실패 인용은 사실 입력에서 빠진다."""
    node_id = uuid.uuid4()
    verified = _verified(
        _claim(node_id=node_id, predicate="status", value="검토 중")
    )
    unverified = replace(
        _claim(
            node_id=node_id,
            predicate="status",
            value="배포됨",
            minutes=5,
        ),
        citation_verified=False,
    )
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[verified, unverified],
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    # 머리말 재료의 사실 입력이 문서 전체의 검증된 인용이다.
    assert narrator.requests[0].summary.statements == (verified.statement,)


def test_contested_candidate_without_a_verified_quote_is_dropped() -> None:
    """검증된 인용이 없는 대조 후보는 요청에서 빠진다.

    프롬프트는 후보 본문을 사실로 싣고 모든 후보를 서술하라고 시킨다.
    근거 없는 후보를 그대로 넘기면 검증되지 않은 값이 산문에 사실로
    나간다.
    """
    node_id = uuid.uuid4()
    verified = _verified(
        _claim(node_id=node_id, predicate="status", value="검토 중")
    )
    unverified = replace(
        _claim(
            node_id=node_id,
            predicate="status",
            value="배포됨",
            minutes=5,
        ),
        citation_verified=False,
    )
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[verified, unverified],
    )
    uow.mutation_proposals.pending = {
        node_id: [
            _contradiction(
                node_id=node_id,
                claims=(verified, unverified),
            )
        ]
    }
    narrator = _FakeNarrator()

    _run(uow, narrator)

    contested = _block_input(narrator, BLOCK_KIND_CONTESTED)
    assert [items for _, items in contested.variants] == [
        (verified.statement,)
    ]
    assert contested.variants[0][0].startswith("검토 중")


def test_contested_block_without_any_verified_quote_is_not_narrated() -> None:
    """후보가 모두 빠지면 그 블록은 서술하지 않고 실패도 아니다."""
    node_id = uuid.uuid4()
    first = replace(
        _claim(node_id=node_id, predicate="status", value="검토 중"),
        citation_verified=False,
    )
    second = replace(
        _claim(
            node_id=node_id,
            predicate="status",
            value="배포됨",
            minutes=5,
        ),
        citation_verified=False,
    )
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[first, second],
    )
    uow.mutation_proposals.pending = {
        node_id: [_contradiction(node_id=node_id, claims=(first, second))]
    }
    narrator = _FakeNarrator()

    result = _run(uow, narrator)

    assert [block.block_kind for block in _blocks(uow)] == [
        BLOCK_KIND_SUMMARY,
        BLOCK_KIND_SUMMARY,
        BLOCK_KIND_SUMMARY,
        BLOCK_KIND_CONTESTED,
    ]
    # 머리말의 근거도 같은 인용이라 검증된 문장이 없어 서술되지 않는다.
    assert narrator.requests == []
    assert result.nodes_failed == 0
    assert result.blocks_narrated == 0
    assert all(block.narrative is None for block in _blocks(uow))


# 관계 종류 requested_by를 쓰는 시험을 위해 어휘에 한 줄을 더한다. 선택
# 규칙 검사가 어휘에 없는 관계 종류를 거르므로, 어휘를 넓히지 않으면 그
# 정의 자체가 컴파일에서 빠진다.
ACTOR_VOCABULARY = VOCABULARY.model_copy(
    update={
        "relation_type_entries": (
            *VOCABULARY.relation_type_entries,
            RelationTypeEntry(
                name="requested_by", definition="요구를 낸 쪽을 가리킨다."
            ),
        )
    }
)


ACTOR_ATTRIBUTES = {
    "external_key": "chat-1",
    "actor": {
        "source_entity_type": "channel_talk_user",
        "emails": ["neo@x.com"],
    },
}


def _actor_edge(
    *,
    source_node_id: uuid.UUID,
    target_node_id: uuid.UUID,
    assertion_text: str = "커넥터 있어?",
    target_display_name: str | None = "팀원A",
    target_attributes: dict | None = None,
) -> StoredRelationEdge:
    """행위자 노드로 이어지는 간선 하나를 만든다.

    도착 쪽 이름과 attributes를 갈아 끼울 수 있게 열어 둔다. 행위자가
    아닌 노드나 이름이 비어 있는 노드도 같은 서식을 거치기 때문이다.
    """
    return StoredRelationEdge(
        id=uuid.uuid4(),
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        assertion_text=assertion_text,
        source_display_name="기능 요청 A",
        target_display_name=target_display_name,
        source_attributes={},
        target_attributes=(
            ACTOR_ATTRIBUTES if target_attributes is None else target_attributes
        ),
    )


def _actor_uow(
    *,
    purpose: str | None = None,
    purposes: tuple[str, ...] | None = None,
    assertion_text: str = "커넥터 있어?",
    target_node_id: uuid.UUID | None = None,
    target_display_name: str | None = "팀원A",
    target_attributes: dict | None = None,
) -> FakeDefinitionUnitOfWork:
    """행위자 간선 하나를 갖는 정의 컴파일용 fake를 세운다."""
    node_id = uuid.uuid4()
    definition = _definition_row(
        spec=_spec(
            relation_paths=[
                {"steps": [{"type": "requested_by", "dir": "out"}]}
            ],
            predicate_sections=["status"],
        )
    )
    uow = FakeDefinitionUnitOfWork(
        definitions=[definition],
        nodes=[(node_id, "기능 요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
        relations=FakeRelationRepository(
            [
                (
                    "requested_by",
                    _actor_edge(
                        source_node_id=node_id,
                        target_node_id=(
                            uuid.uuid4()
                            if target_node_id is None
                            else target_node_id
                        ),
                        assertion_text=assertion_text,
                        target_display_name=target_display_name,
                        target_attributes=target_attributes,
                    ),
                )
            ]
        ),
    )
    chosen = purposes if purposes is not None else ()
    if purpose is not None:
        chosen = (purpose, *chosen)
    if chosen:
        uow.artifact_definitions.channel_purposes = {
            definition[1]: tuple(chosen),
        }
    return uow


def _run_with_actor_vocabulary(uow, narrator=None):
    """requested_by가 실린 어휘로 정의 순회 컴파일을 돌린다."""
    return compile_definition_artifacts(
        uow,
        workspace_id=WORKSPACE,
        vocabulary=ACTOR_VOCABULARY,
        narrator=narrator,
    )


def _relation_block(uow):
    """계류 변경안에서 관계 절 블록 하나를 꺼낸다."""
    return next(
        block
        for block in _blocks(uow)
        if block.block_kind == BLOCK_KIND_RELATION_SECTION
    )


def test_relation_narration_gets_named_edges_and_hints_with_exposure() -> None:
    """관계 절은 노출을 적용한 간선 줄과 원문 힌트를 갈라 넘긴다."""
    uow = _actor_uow(purpose="voc.request_status_tracking")
    narrator = _FakeNarrator()

    _run_with_actor_vocabulary(uow, narrator)

    relation_input = _relation_request(narrator)
    assert relation_input.edges == (
        "기능 요청 A → requested_by → 팀원A (neo@x.com)",
    )
    assert relation_input.hints == ("커넥터 있어?",)
    assert relation_input.statements == ()


def test_multiline_assertion_stays_a_single_hint() -> None:
    """여러 줄 원문도 힌트 하나로 접혀 사실 입력을 늘리지 않는다."""
    uow = _actor_uow(
        purpose="voc.request_status_tracking",
        assertion_text="첫 줄\n둘째 줄",
    )
    narrator = _FakeNarrator()

    _run_with_actor_vocabulary(uow, narrator)

    relation_input = _relation_request(narrator)
    assert relation_input.edges == (
        "기능 요청 A → requested_by → 팀원A (neo@x.com)",
    )
    assert relation_input.hints == ("첫 줄 둘째 줄",)


def test_anonymous_exposure_hides_actor_name() -> None:
    """anonymous 노출은 행위자 이름을 역할 표기로 덮는다.

    도메인 preset에 anonymous를 걸어 둔 자리가 아직 없어 컴파일 경로로는
    닿지 않는다. 서식 자체가 노출 수준을 지키는지만 직접 본다.
    """
    edge = _actor_edge(
        source_node_id=uuid.uuid4(), target_node_id=uuid.uuid4()
    )

    line = _actor_edge_line("anonymous")(edge, "requested_by")

    assert line == "기능 요청 A → requested_by → 고객"


def test_relation_block_hash_differs_by_exposure() -> None:
    """노출 수준이 다르면 같은 그래프라도 관계 블록 지문이 갈린다."""
    named = _actor_uow(purpose=None)
    with_email = _actor_uow(purpose="voc.request_status_tracking")

    _run_with_actor_vocabulary(named)
    _run_with_actor_vocabulary(with_email)

    assert "팀원A (neo@x.com)" not in _relation_block(named).body
    assert block_content_hash(_relation_block(named)) != block_content_hash(
        _relation_block(with_email)
    )


def test_actor_exposure_follows_the_first_purpose() -> None:
    """목적이 여럿이어도 첫 목적으로 행위자 노출 수준을 정한다.

    노출은 도메인이 정하고 목적은 그 도메인을 가리키는 손잡이라, 목록을
    받아도 첫 목적 하나면 수준이 정해진다.
    """
    uow = _actor_uow(
        purposes=("voc.request_status_tracking", "voc.complaint_patterns")
    )

    _run_with_actor_vocabulary(uow)

    assert "팀원A (neo@x.com)" in _relation_block(uow).body


@pytest.mark.parametrize(
    "target_attributes",
    [None, {}],
    ids=["actor", "non_actor"],
)
def test_multiline_target_name_stays_one_edge_line(
    target_attributes: dict | None,
) -> None:
    """도착 쪽 이름에 줄바꿈이 있어도 간선 줄은 하나로 남는다.

    본문은 줄 단위로 다시 갈리므로, 이름의 줄바꿈이 남으면 없는 간선
    줄이 하나 생기고 진짜 도착 노드가 사라진다.
    """
    uow = _actor_uow(
        purpose=None,
        target_display_name="제품\n관리",
        target_attributes=target_attributes,
    )
    narrator = _FakeNarrator()

    _run_with_actor_vocabulary(uow, narrator)

    assert _relation_request(narrator).edges == (
        "기능 요청 A → requested_by → 제품 관리",
    )
    assert _relation_block(uow).body.split("\n") == [
        "기능 요청 A → requested_by → 제품 관리",
        "  ↳ 커넥터 있어?",
    ]


@pytest.mark.parametrize(
    "target_attributes",
    [None, {}],
    ids=["actor", "non_actor"],
)
def test_empty_target_name_falls_back_to_the_node_id(
    target_attributes: dict | None,
) -> None:
    """도착 쪽 이름이 없으면 노드 식별자로 대신한다."""
    target_node_id = uuid.uuid4()
    uow = _actor_uow(
        purpose=None,
        target_node_id=target_node_id,
        target_display_name=None,
        target_attributes=target_attributes,
    )
    narrator = _FakeNarrator()

    _run_with_actor_vocabulary(uow, narrator)

    assert _relation_request(narrator).edges == (
        f"기능 요청 A → requested_by → {target_node_id}",
    )
