"""문서 맨 앞에 서는 머리말 블록 셋의 결정론과 서술 입력을 확인한다.

머리말은 한 줄 요약·원하는 결과·요청 배경 세 섹션이고, 각각 summary
블록 하나로 선다. 문서를 열자마자 읽는 자리라 본문이 실행마다 흔들리면
안 된다. 본문·claim 장부·근거 순서를 입력 순서와 무관하게 고정하는 것이
여기서 지키려는 계약이고, 산문만 LLM이 쓴다.
"""

from __future__ import annotations

import uuid

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    _SUMMARY_SOURCE_LIMIT,
)
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _blocks
from catchup.tests.knowledge_maintenance.test_compile_block_narration import (
    _contradiction,
)
from catchup.tests.knowledge_maintenance.test_compile_block_narration import (
    _FakeNarrator,
)
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _run
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _uow
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _verified
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

NODE = (uuid.uuid4(), "요청 A", "feature_request", "active")


def _two_claims():
    """같은 노드에 붙는, 관찰 시각이 다른 claim 두 개를 만든다."""
    node_id = NODE[0]
    first = _verified(_claim(node_id=node_id, value="검토 중", minutes=0))
    second = _verified(_claim(node_id=node_id, value="진행 중", minutes=30))
    return first, second


def test_summary_blocks_are_first_and_aggregate_claims() -> None:
    """머리말 세 블록이 정해진 순서로 맨 앞에 서고 claim을 합쳐 가리킨다."""
    first, second = _two_claims()
    uow = _uow(nodes=[NODE], claims=[first, second])

    _run(uow)

    summaries = _blocks(uow)[:3]
    assert [block.block_kind for block in summaries] == [
        BLOCK_KIND_SUMMARY
    ] * 3
    assert [block.heading for block in summaries] == [
        "one_line_summary",
        "desired_outcome",
        "background",
    ]
    for summary in summaries:
        assert set(summary.claim_ids) == {first.id, second.id}
        assert summary.body.startswith("claim 2건")
        assert summary.narrative is None


def test_summary_body_records_counts_and_report_window() -> None:
    """본문 한 줄이 건수와 최초·최근 보고 시각을 정해진 순서로 적는다."""
    first, second = _two_claims()
    uow = _uow(nodes=[NODE], claims=[first, second])

    _run(uow)

    # 세 블록에 같은 집계 한 줄이 실린다.
    for summary in _blocks(uow)[:3]:
        assert summary.body == (
            "claim 2건 · 관계 0건 · 열린 질문 0건"
            f" · 최초 보고 {first.observed_at.isoformat()}"
            f" · 최근 보고 {second.observed_at.isoformat()}"
        )


def test_summary_body_is_deterministic_across_runs() -> None:
    """claim이 들어오는 순서가 달라도 같은 지문이 나온다."""
    first, second = _two_claims()
    forward = _uow(nodes=[NODE], claims=[first, second])
    backward = _uow(nodes=[NODE], claims=[second, first])

    _run(forward)
    _run(backward)

    assert block_content_hash(_blocks(forward)[0]) == block_content_hash(
        _blocks(backward)[0]
    )


def test_summary_is_narrated_with_all_statements() -> None:
    """머리말 서술 요청에 문서의 검증된 인용이 모두 실린다."""
    first, second = _two_claims()
    uow = _uow(nodes=[NODE], claims=[first, second])
    narrator = _FakeNarrator()

    _run(uow, narrator)

    summary_input = narrator.requests[0].summary
    assert summary_input.block_kind == BLOCK_KIND_SUMMARY
    assert set(summary_input.statements) == {first.statement, second.statement}
    assert summary_input.topic_hint == _blocks(uow)[0].body
    assert summary_input.edges == ()
    assert _blocks(uow)[0].narrative


def test_empty_document_makes_no_summary_blocks() -> None:
    """실을 내용이 없으면 문서 자체가 서지 않는다."""
    uow = _uow(nodes=[NODE], claims=[])

    _run(uow)

    assert uow.artifacts.pending_rows() == []


def test_summary_sources_keep_the_most_recent_within_the_limit() -> None:
    """근거가 상한을 넘으면 오래된 것부터 빠지고 최근 것이 남는다."""
    node_id = NODE[0]
    claims = [
        _claim(node_id=node_id, value=f"값 {index}", minutes=index)
        for index in range(_SUMMARY_SOURCE_LIMIT + 1)
    ]
    uow = _uow(nodes=[NODE], claims=claims)

    _run(uow)

    summary = _blocks(uow)[0]
    assert len(summary.sources) == _SUMMARY_SOURCE_LIMIT
    carried = {source.claim_id for source in summary.sources}
    assert claims[0].id not in carried
    assert claims[-1].id in carried
    # 본문의 보고 시각은 자르기 전 근거 전체에서 센다.
    assert summary.body.endswith(
        f"최초 보고 {claims[0].observed_at.isoformat()}"
        f" · 최근 보고 {claims[-1].observed_at.isoformat()}"
    )
    # 장부는 자르지 않는다. 요약은 문서 전체의 claim을 가리킨다.
    assert len(summary.claim_ids) == len(claims)


def test_same_source_in_two_blocks_is_carried_once() -> None:
    """두 블록이 같은 인용을 가리키면 머리말에는 한 번만 실린다."""
    node_id = NODE[0]
    claim = _claim(node_id=node_id)
    uow = _uow(nodes=[NODE], claims=[claim])
    # 값이 하나뿐이라 대조가 서지 않아, 같은 claim이 claim 절과 열린
    # 질문 양쪽의 근거가 된다.
    uow.mutation_proposals.pending = {
        node_id: [_contradiction(node_id=node_id, claims=(claim,))]
    }

    _run(uow)

    blocks = _blocks(uow)
    summary = blocks[0]
    assert [block.block_kind for block in blocks[3:]] == [
        "claim_section",
        "open_question",
    ]
    assert len(summary.sources) == 1
    assert summary.sources[0].claim_id == claim.id
    assert summary.body.startswith("claim 1건 · 관계 0건 · 열린 질문 1건")


def test_relation_only_document_stands_without_summary() -> None:
    """claim 없이 관계만 있는 문서는 머리말 없이 그대로 선다.

    머리말은 claim 장부를 요구하는 블록이라 빈 장부로 세울 수 없다. 그
    자리에서 문서까지 접으면 관계만 아는 대상의 카드가 사라진다.
    """
    node_id = NODE[0]
    uow = FakeDefinitionUnitOfWork(
        definitions=[
            _definition_row(
                spec=_spec(
                    relation_paths=[
                        {"steps": [{"type": "owned_by", "dir": "out"}]}
                    ],
                    predicate_sections=[],
                )
            )
        ],
        nodes=[NODE],
        claims=[],
        relations=FakeRelationRepository(
            [
                (
                    "owned_by",
                    StoredRelationEdge(
                        id=uuid.uuid4(),
                        source_node_id=node_id,
                        target_node_id=uuid.uuid4(),
                        assertion_text="요청 A는 결제팀이 맡는다",
                        source_display_name="요청 A",
                        target_display_name="결제팀",
                    ),
                )
            ]
        ),
    )

    result = _run(uow)

    assert result.proposals_created == 1
    assert [block.block_kind for block in _blocks(uow)] == [
        BLOCK_KIND_RELATION_SECTION
    ]
