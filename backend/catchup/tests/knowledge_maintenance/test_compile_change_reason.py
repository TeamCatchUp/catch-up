"""재컴파일이 바뀐 블록에만 수정 이유를 붙이는지 fake로 확인한다.

문서를 다시 여는 사람이 먼저 묻는 것은 "왜 달라졌나"다. 그 답을 붙이는
자리를 잘못 잡으면 첫 컴파일부터 LLM이 돌거나, 새로 생긴 절에까지 "왜
바뀌었나"를 묻게 된다. 호출 횟수와 어느 블록에 문장이 붙었는지가 곧
규칙이다.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _blocks
from catchup.tests.knowledge_maintenance.test_compile_block_narration import (
    _FakeNarrator,
)
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _pending
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _run
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _uow
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _verified
from catchup.tests.knowledge_maintenance.test_compile_definition_artifacts import _claim


def _explained_headings(narrator: _FakeNarrator) -> list[str]:
    """수정 이유를 물은 블록의 제목만 모은다."""
    return [request.heading for request in narrator.explanations]


def _reasons(uow) -> dict[str, str | None]:
    """계류 변경안 블록의 제목별 수정 이유를 모은다."""
    return {block.heading: block.change_reason for block in _blocks(uow)}


def _two_section_uow(node_id: uuid.UUID):
    """status·priority 두 절을 쓸 수 있는 정의로 fake를 세운다."""
    return _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[_verified(_claim(node_id=node_id, predicate="status"))],
        sections=("status", "priority"),
    )


def _publish_pending(uow, revision_number: int = 1) -> None:
    """계류 변경안 하나를 승인해 그대로 판으로 낸다."""
    row = _pending(uow)
    uow.artifacts.mark_approved(proposal_id=row["id"], reviewer="사람")
    uow.artifacts.add_revision(
        artifact_id=row["artifact_id"],
        revision_number=revision_number,
        blocks=row["blocks"],
        source_proposal_id=row["id"],
    )


def _add_priority_claim(uow, node_id: uuid.UUID) -> None:
    """새 절이 생기도록 priority claim을 하나 붙인다."""
    uow.knowledge_candidates.claims.append(
        _verified(
            _claim(
                node_id=node_id,
                predicate="priority",
                value="높음",
                minutes=5,
            )
        )
    )


def _add_second_status_claim(uow, node_id: uuid.UUID) -> None:
    """status 절 본문이 바뀌도록 claim을 하나 더 붙인다."""
    uow.knowledge_candidates.claims.append(
        _verified(
            _claim(
                node_id=node_id,
                predicate="status",
                value="검토 중",
                minutes=5,
            )
        )
    )


def test_first_compile_has_no_change_reason() -> None:
    """발행 판이 없으면 비교할 이전 내용이 없어 아무것도 묻지 않는다."""
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    narrator = _FakeNarrator()

    result = _run(uow, narrator)

    assert narrator.explanations == []
    assert result.blocks_explained == 0
    assert result.blocks_explanation_reused == 0
    assert all(reason is None for reason in _reasons(uow).values())


def test_modified_block_gets_llm_reason_added_block_does_not() -> None:
    """짝이 있는 블록만 이유를 받고 새로 생긴 절은 비워 둔다."""
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)
    _add_second_status_claim(uow, node_id)

    result = _run(uow, narrator)

    reasons = _reasons(uow)
    assert _explained_headings(narrator) == ["status"]
    assert reasons["status"] == "status 블록이 바뀐 이유다."
    assert result.blocks_explained == 1
    assert result.blocks_explanation_reused == 0


def test_summary_block_gets_no_change_reason() -> None:
    """요약은 아래 블록을 센 값이라 수정 이유를 붙이지 않는다."""
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)
    # 절이 하나 늘면 요약 본문도 함께 바뀐다.
    _add_priority_claim(uow, node_id)

    result = _run(uow, narrator)

    summary_heading = next(
        block.heading
        for block in _blocks(uow)
        if block.block_kind == BLOCK_KIND_SUMMARY
    )
    assert _reasons(uow)[summary_heading] is None
    assert summary_heading not in _explained_headings(narrator)
    assert result.blocks_explained == 0


def test_explanation_request_carries_before_and_after_statements() -> None:
    """이유를 묻는 요청에 앞뒤 문장과 새로 붙은 인용이 실린다."""
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)
    _add_second_status_claim(uow, node_id)

    _run(uow, narrator)

    request = next(
        item for item in narrator.explanations if item.heading == "status"
    )
    assert len(request.before_statements) == 1
    assert len(request.after_statements) == 2
    assert request.before_statements[0] in request.after_statements
    assert set(request.new_sources) == set(request.after_statements) - set(
        request.before_statements
    )


def test_unchanged_recompile_calls_explain_zero_times() -> None:
    """내용이 그대로면 이유도 묻지 않는다."""
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)

    result = _run(uow, narrator)

    assert result.unchanged_skipped == 1
    assert narrator.explanations == []


def test_same_base_reuses_reason_without_call() -> None:
    """기준 판이 같으면 지문이 같은 블록의 이유를 그대로 다시 쓴다."""
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)
    _add_second_status_claim(uow, node_id)
    _run(uow, narrator)
    # 계류에 실린 문장을 새로 만든 문장과 갈라 놓아야 재사용이 보인다.
    pending = _pending(uow)
    pending["blocks"] = tuple(
        block
        if block.block_kind == BLOCK_KIND_SUMMARY
        else replace(block, change_reason="계류에 실린 이유다.")
        for block in pending["blocks"]
    )
    narrator.explanations.clear()
    _add_priority_claim(uow, node_id)

    result = _run(uow, narrator)

    reasons = _reasons(uow)
    assert _explained_headings(narrator) == []
    assert reasons["status"] == "계류에 실린 이유다."
    assert reasons["priority"] is None
    assert result.blocks_explained == 0
    assert result.blocks_explanation_reused == 1


def test_explain_error_fails_node() -> None:
    """이유를 받지 못하면 그 문서 하나를 접는다."""
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    _run(uow, _FakeNarrator())
    _publish_pending(uow)
    _add_second_status_claim(uow, node_id)

    narrator = _FakeNarrator(explain_error=NarrationError("모델이 답하지 않았다"))

    result = _run(uow, narrator)

    assert result.nodes_failed == 1
    assert uow.artifacts.pending_rows() == []


def test_no_narrator_leaves_reason_none() -> None:
    """narrator가 없으면 이유 단계 전체를 건너뛴다."""
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    _run(uow, _FakeNarrator())
    _publish_pending(uow)
    _add_priority_claim(uow, node_id)

    result = _run(uow)

    assert result.blocks_explained == 0
    assert result.blocks_explanation_reused == 0
    assert all(reason is None for reason in _reasons(uow).values())
