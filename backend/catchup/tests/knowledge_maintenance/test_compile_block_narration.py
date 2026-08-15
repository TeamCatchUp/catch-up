"""컴파일이 언제 산문을 부르고 언제 부르지 않는지 fake로 확인한다.

호출 횟수가 곧 규칙이다. 무변경 재컴파일에 LLM이 돌면 검토 큐가 흔들리기
전에 비용부터 새고, 한 블록만 바뀐 재컴파일에 문서 전체가 다시 쓰이면
검수자가 진짜 변화를 못 찾는다.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from structlog.testing import capture_logs

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.preset_catalog import DEFAULT_PURPOSE_SENTENCE
from catchup.knowledge_maintenance.domain.preset_catalog import (
    DEFAULT_STYLE_INSTRUCTION,
)
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.knowledge_maintenance.ports.narrator import NarrationRequest
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
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


class _FakeNarrator:
    """호출을 기록하고 고정 문장을 돌려주는 서술기다."""

    def __init__(self, error: Exception | None = None) -> None:
        self.requests: list[NarrationRequest] = []
        self.error = error

    def narrate(self, request: NarrationRequest) -> str:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return f"{request.heading} 절을 설명하는 문장이다."


def _verified(claim: StoredClaimCandidate) -> StoredClaimCandidate:
    """인용 대조를 통과한 claim으로 바꾼다.

    `_claim` 헬퍼의 기본값은 대조 판정 없음(None)이라 그대로 쓰면 블록에
    검증된 인용이 하나도 없어 서술 대상이 되지 않는다. 서술 규칙을 보는
    시험이므로 여기서 판정을 참으로 세운다.
    """
    return replace(claim, citation_verified=True)


def _uow(
    *, claims, nodes, styles=None, sections=("status",)
) -> FakeDefinitionUnitOfWork:
    """정의 하나·노드·claim으로 fake UnitOfWork를 세운다."""
    definition = _definition_row(
        spec=_spec(predicate_sections=list(sections))
    )
    uow = FakeDefinitionUnitOfWork(
        definitions=[definition], nodes=nodes, claims=claims
    )
    if styles:
        uow.artifact_definitions.channel_styles = {
            definition[1]: styles,
        }
    return uow


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
    """첫 컴파일은 서술 가능한 블록 수만큼 부른다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id))],
    )
    narrator = _FakeNarrator()

    result = _run(uow, narrator)

    blocks = _blocks(uow)
    narratable = [block for block in blocks if block.sources]
    assert len(narrator.requests) == len(narratable)
    assert result.blocks_narrated == len(narratable)
    assert all(block.narrative for block in narratable)


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

    assert [item.heading for item in narrator.requests] == ["priority"]
    assert result.blocks_narrated == 1
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

    assert sorted(item.heading for item in narrator.requests) == [
        "priority",
        "status",
    ]
    assert result.blocks_narrated == 2
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

    relation_request = next(
        item
        for item in narrator.requests
        if item.block_kind == BLOCK_KIND_RELATION_SECTION
    )
    assert relation_request.statements == ()
    assert relation_request.edges == ("요청 A는 결제팀이 맡는다",)
    assert result.blocks_narrated == 2
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
        styles="style.faq",
    )
    narrator = _FakeNarrator()

    _run(uow, narrator)

    assert "자주 묻는 질문" in narrator.requests[0].style_instruction


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

    assert narrator.requests[0].statements == (verified.statement,)
