"""문서 맨 앞에 서는 summary 블록의 결정론과 서술 입력을 확인한다.

summary는 문서를 열자마자 읽는 첫 블록이라 본문이 실행마다 흔들리면 안
된다. 본문·claim 장부·근거 순서를 입력 순서와 무관하게 고정하는 것이
여기서 지키려는 계약이고, 산문만 LLM이 쓴다.
"""

from __future__ import annotations

import uuid

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _blocks
from catchup.tests.knowledge_maintenance.test_compile_block_narration import (
    _FakeNarrator,
)
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _run
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _uow
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _verified
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import _claim

NODE = (uuid.uuid4(), "요청 A", "feature_request", "active")


def _two_claims():
    """같은 노드에 붙는, 관찰 시각이 다른 claim 두 개를 만든다."""
    node_id = NODE[0]
    first = _verified(_claim(node_id=node_id, value="검토 중", minutes=0))
    second = _verified(_claim(node_id=node_id, value="진행 중", minutes=30))
    return first, second


def test_summary_block_is_first_and_aggregates_claims() -> None:
    """summary가 맨 앞에 서고 모든 블록의 claim을 합쳐 가리킨다."""
    first, second = _two_claims()
    uow = _uow(nodes=[NODE], claims=[first, second])

    _run(uow)

    blocks = _blocks(uow)
    summary = blocks[0]
    assert summary.block_kind == BLOCK_KIND_SUMMARY
    assert set(summary.claim_ids) == {first.id, second.id}
    assert summary.body.startswith("claim 2건")
    assert summary.narrative is None


def test_summary_body_records_counts_and_report_window() -> None:
    """본문 한 줄이 건수와 최초·최근 보고 시각을 정해진 순서로 적는다."""
    first, second = _two_claims()
    uow = _uow(nodes=[NODE], claims=[first, second])

    _run(uow)

    summary = _blocks(uow)[0]
    assert summary.body == (
        "claim 2건 · 관계 0건 · 열린 질문 0건"
        f" · 최초 보고 {first.observed_at.isoformat()}"
        f" · 최근 보고 {second.observed_at.isoformat()}"
    )
    assert summary.heading == _title(uow)


def _title(uow) -> str:
    """이번 컴파일이 문서에 붙인 제목을 꺼낸다."""
    titles = list(uow.artifacts.titles.values())
    assert len(titles) == 1
    return titles[0]


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
    """summary 서술 요청에 문서의 검증된 인용이 모두 실린다."""
    first, second = _two_claims()
    uow = _uow(nodes=[NODE], claims=[first, second])
    narrator = _FakeNarrator()

    _run(uow, narrator)

    request = narrator.requests[0]
    assert request.block_kind == BLOCK_KIND_SUMMARY
    assert set(request.statements) == {first.statement, second.statement}
    assert request.topic_hint == _blocks(uow)[0].body
    assert request.edges == ()
    assert _blocks(uow)[0].narrative


def test_empty_document_makes_no_summary() -> None:
    """실을 내용이 없으면 문서 자체가 서지 않는다."""
    uow = _uow(nodes=[NODE], claims=[])

    _run(uow)

    assert uow.artifacts.pending_rows() == []
