"""재컴파일이 바뀐 블록에만 수정 이유를 붙이는지 fake로 확인한다.

문서를 다시 여는 사람이 먼저 묻는 것은 "왜 달라졌나"다. 그 답을 붙이는
자리를 잘못 잡으면 첫 컴파일부터 LLM이 돌거나, 새로 생긴 절에까지 "왜
바뀌었나"를 묻게 된다. 호출 횟수와 어느 블록에 문장이 붙었는지가 곧
규칙이다.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_RELATION_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_SUMMARY
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
from catchup.knowledge_maintenance.services.traverse_relations import (
    RELATION_HINT_PREFIX,
)
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _blocks
from catchup.tests.knowledge_maintenance.test_compile_block_narration import (
    _FakeNarrator,
)
from catchup.tests.knowledge_maintenance.test_compile_block_narration import _pending
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
    """머리말은 아래 블록을 센 값이라 세 블록 모두 수정 이유가 없다.

    제외 기준이 block_kind라 머리말이 몇 블록이든 함께 빠진다.
    """
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)
    # 절이 하나 늘면 요약 본문도 함께 바뀐다.
    _add_priority_claim(uow, node_id)

    result = _run(uow, narrator)

    summary_headings = [
        block.heading
        for block in _blocks(uow)
        if block.block_kind == BLOCK_KIND_SUMMARY
    ]
    assert len(summary_headings) == 3
    for heading in summary_headings:
        assert _reasons(uow)[heading] is None
        assert heading not in _explained_headings(narrator)
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


def _edge(
    *,
    source_node_id: uuid.UUID,
    target_display_name: str,
    assertion_text: str,
) -> StoredRelationEdge:
    """관계 절 본문에 실릴 간선 하나를 만든다."""
    return StoredRelationEdge(
        id=uuid.uuid4(),
        source_node_id=source_node_id,
        target_node_id=uuid.uuid4(),
        assertion_text=assertion_text,
        source_display_name="요청 A",
        target_display_name=target_display_name,
    )


def _relation_uow(node_id: uuid.UUID, edges) -> FakeDefinitionUnitOfWork:
    """관계 절 하나를 쓰는 정의로 fake를 세운다."""
    return FakeDefinitionUnitOfWork(
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
            [("owned_by", edge) for edge in edges]
        ),
    )


def _relation_heading(uow) -> str:
    """계류 변경안에서 관계 절의 제목을 꺼낸다."""
    return next(
        block.heading
        for block in _blocks(uow)
        if block.block_kind == BLOCK_KIND_RELATION_SECTION
    )


def test_modified_relation_section_explains_from_edge_lines() -> None:
    """관계 절이 바뀌면 앞뒤 사실 입력을 본문 간선 줄로 채운다."""
    node_id = uuid.uuid4()
    first = _edge(
        source_node_id=node_id,
        target_display_name="결제팀",
        assertion_text="요청 A는 결제팀이 맡는다",
    )
    uow = _relation_uow(node_id, [first])
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)
    second = _edge(
        source_node_id=node_id,
        target_display_name="정산팀",
        assertion_text="요청 A는 정산팀도 맡는다",
    )
    uow.relations.edges.append(("owned_by", second))

    result = _run(uow, narrator)

    heading = _relation_heading(uow)
    request = next(
        item for item in narrator.explanations if item.heading == heading
    )
    assert request.before_statements == ("요청 A → owned_by → 결제팀",)
    assert set(request.after_statements) == {
        "요청 A → owned_by → 결제팀",
        "요청 A → owned_by → 정산팀",
    }
    assert request.new_sources == ("요청 A → owned_by → 정산팀",)
    assert result.blocks_explained == 1
    reasons = _reasons(uow)
    assert reasons[heading] == f"{heading} 블록이 바뀐 이유다."


def test_relation_explanation_drops_hint_lines() -> None:
    """관계 절의 힌트 줄은 앞뒤 사실 입력에 넣지 않는다."""
    node_id = uuid.uuid4()
    first = _edge(
        source_node_id=node_id,
        target_display_name="결제팀",
        assertion_text="요청 A는 결제팀이 맡는다",
    )
    uow = _relation_uow(node_id, [first])
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)
    second = _edge(
        source_node_id=node_id,
        target_display_name="정산팀",
        assertion_text="요청 A는 정산팀도 맡는다",
    )
    uow.relations.edges.append(("owned_by", second))

    _run(uow, narrator)

    heading = _relation_heading(uow)
    request = next(
        item for item in narrator.explanations if item.heading == heading
    )
    lines = (
        *request.before_statements,
        *request.after_statements,
        *request.new_sources,
    )
    assert lines
    assert all(not line.startswith(RELATION_HINT_PREFIX) for line in lines)
    assert all("맡는다" not in line for line in lines)


def test_modified_block_without_any_statement_is_not_explained() -> None:
    """앞뒤가 모두 비면 묻지 않고 수정 이유를 비워 둔다."""
    node_id = uuid.uuid4()
    uow = _uow(
        nodes=[(node_id, "요청 A", "feature_request", "active")],
        claims=[replace(_claim(node_id=node_id), citation_verified=False)],
    )
    narrator = _FakeNarrator()
    _run(uow, narrator)
    _publish_pending(uow)
    uow.knowledge_candidates.claims.append(
        replace(
            _claim(
                node_id=node_id,
                predicate="status",
                value="검토 중",
                minutes=5,
            ),
            citation_verified=False,
        )
    )

    result = _run(uow, narrator)

    assert narrator.explanations == []
    assert result.blocks_explained == 0
    assert _reasons(uow)["status"] is None


class _PublishingNarrator(_FakeNarrator):
    """머리말을 서술하는 동안 새 판이 발행되는 상황을 흉내 낸다.

    컴파일은 기준 판을 서술 앞에서 읽고 저장은 서술 뒤에 한다. 그 사이가
    LLM 호출만큼 벌어져 있어, 다른 검토자가 계류 변경안을 승인하면 기준
    판이 바뀐 채로 저장이 이어진다. 첫 서술 한 번에만 끼어들어 그 순간을
    만든다.
    """

    def __init__(self, uow, revision_number: int) -> None:
        super().__init__()
        self._uow = uow
        self._revision_number = revision_number
        self.published = False

    def narrate_document(self, request):
        if not self.published:
            self.published = True
            _publish_pending(self._uow, self._revision_number)
        return super().narrate_document(request)


def test_publish_during_narration_drops_the_stale_proposal() -> None:
    """서술 중 발행이 끼어들면 낡은 기준의 변경안을 저장하지 않는다.

    낡은 기준을 적은 계류가 저장되면 발행이 거부하는데 다음 컴파일은 그
    계류의 지문을 보고 무변경으로 건너뛰므로 갈아 주지도 않는다. 그래서
    어긋남을 본 노드는 저장도 접기도 하지 않고 물러난다.
    """
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    _run(uow, _FakeNarrator())
    _publish_pending(uow, 1)
    _add_priority_claim(uow, node_id)
    _run(uow, _FakeNarrator())
    _add_second_status_claim(uow, node_id)
    first_revision = uow.artifacts.revisions[0]["id"]

    narrator = _PublishingNarrator(uow, 2)
    result = _run(uow, narrator)

    assert narrator.published is True
    assert result.proposals_created == 0
    assert result.proposals_conflicted == 1
    assert result.proposals_abandoned == 0
    # 저장을 접어도 이미 쓴 서술 수는 그대로 센다. 감사 로그가 실제 호출
    # 결과를 세야 하므로 물러나는 경로에서도 버리지 않는다. 요청의
    # summary 한 칸이 최상위 블록 3개를 채우므로 그만큼을 세어 맞춘다.
    expected_narrated = sum(
        len(request.blocks) + (3 if request.summary is not None else 0)
        for request in narrator.requests
    )
    assert result.blocks_narrated == expected_narrated
    # 낡은 기준을 적은 계류가 남지 않았다. 끼어든 승인으로 이전 계류는
    # approved가 됐으므로 계류는 하나도 없는 것이 맞다.
    assert uow.artifacts.pending_rows() == []
    assert all(
        row["base_revision_id"] != first_revision
        or row["status"] != "pending"
        for row in uow.artifacts.by_key.values()
    )
    # 기존 계류를 접지 않았다. 접었다면 승인된 행이 abandoned로 덮였다.
    assert all(
        row["status"] != "abandoned" for row in uow.artifacts.by_key.values()
    )


def test_next_compile_recovers_on_the_new_base() -> None:
    """물러난 다음 컴파일이 새 기준 판 위에 변경안을 다시 세운다.

    이 픽스처에서는 새 판에 없는 status claim이 하나 더 붙어 있으므로
    내용이 판과 달라 계류가 새로 생기는 쪽이다. 내용이 판과 같았다면
    올릴 것이 없으니 건너뛰는 것이 맞다.
    """
    node_id = uuid.uuid4()
    uow = _two_section_uow(node_id)
    _run(uow, _FakeNarrator())
    _publish_pending(uow, 1)
    _add_priority_claim(uow, node_id)
    _run(uow, _FakeNarrator())
    _add_second_status_claim(uow, node_id)
    _run(uow, _PublishingNarrator(uow, 2))
    second_revision = uow.artifacts.revisions[1]["id"]

    result = _run(uow, _FakeNarrator())

    assert result.proposals_created == 1
    assert result.proposals_conflicted == 0
    assert _pending(uow)["base_revision_id"] == second_revision
