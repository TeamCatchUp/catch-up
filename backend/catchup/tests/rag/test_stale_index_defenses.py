"""Surgical defenses against stale [N] index references leaking into user-visible
answers.

배경: agent_reasoning이 reuse 턴에 재공급되거나, 같은 턴 내에서도 grouping 도입
이후 인덱스 체계가 어긋날 때 LLM이 본문에 stale `[14]` 같은 좌표를 그대로 박는
환각이 관측됨. 이 테스트는 두 군데에 방어선을 친다:

1. `sanitize_agent_reasoning` — agent_reasoning을 final-answer LLM에 넘기기 전,
   `<key_document_indices>` 태그 제거에 더해 본문 안의 inline `[N]`/`**N**`/
   `N번 문서` 패턴까지 정제한다.
2. `scrub_orphan_indices` — final 답변 본문에서 현재 표시 인덱스 범위 밖의 `[N]`
   참조를 제거한다 (사용자가 깨진 인용 아이콘을 보지 않도록).
"""

from __future__ import annotations

from catchup.rag.nodes.utils import sanitize_agent_reasoning
from catchup.rag.nodes.utils import scrub_orphan_indices


class TestSanitizeAgentReasoning:
    def test_strips_inline_bracket_index_in_prose(self):
        reasoning = "Document [14] explains the formula clearly."
        out = sanitize_agent_reasoning(reasoning)
        assert "[14]" not in out
        # 주변 산문은 살아있어야 한다.
        assert "Document" in out
        assert "explains the formula clearly." in out

    def test_strips_multiple_inline_bracket_indices(self):
        reasoning = "Refer to [1], [3], and [14] for evidence."
        out = sanitize_agent_reasoning(reasoning)
        assert "[1]" not in out
        assert "[3]" not in out
        assert "[14]" not in out
        assert "Refer to" in out

    def test_strips_markdown_emphasis_on_bare_numbers(self):
        reasoning = "The key documents are **2** and **14**."
        out = sanitize_agent_reasoning(reasoning)
        assert "**2**" not in out
        assert "**14**" not in out
        assert "The key documents are" in out

    def test_strips_korean_number_doc_phrase(self):
        reasoning = "14번 문서는 토큰 사용량 계산식을 담고 있다."
        out = sanitize_agent_reasoning(reasoning)
        assert "14번 문서" not in out
        # 정보는 어떤 식으로든 탈색되더라도 산문 자체는 유지되어야 한다.
        assert "토큰 사용량" in out

    def test_preserves_non_numeric_brackets(self):
        # `[note]`, `[example]` 같이 숫자가 아닌 대괄호는 인용이 아니므로 유지.
        reasoning = "See [note] and [example] for context."
        out = sanitize_agent_reasoning(reasoning)
        assert "[note]" in out
        assert "[example]" in out

    def test_handles_none_or_empty(self):
        assert sanitize_agent_reasoning("") == ""
        assert sanitize_agent_reasoning(None) is None


class TestScrubOrphanIndices:
    def test_removes_out_of_range_index_from_body(self):
        body = "결과는 다음과 같습니다 [2]. 자세한 내용은 [14]를 참고하세요."
        out = scrub_orphan_indices(body, valid_indices={1, 2, 3, 7})
        assert "[14]" not in out
        # 유효한 인용은 보존되어야 한다.
        assert "[2]" in out

    def test_preserves_all_valid_indices(self):
        body = "정합니다 [1][2][3]."
        out = scrub_orphan_indices(body, valid_indices={1, 2, 3})
        assert out == body

    def test_removes_chained_orphan_indices(self):
        body = "근거 [3][14][20]에 따라..."
        out = scrub_orphan_indices(body, valid_indices={1, 2, 3})
        assert "[14]" not in out
        assert "[20]" not in out
        assert "[3]" in out

    def test_no_op_when_no_indices_present(self):
        body = "그냥 평범한 답변입니다."
        out = scrub_orphan_indices(body, valid_indices={1, 2})
        assert out == body

    def test_empty_valid_indices_strips_all(self):
        body = "참고 [1][2]"
        out = scrub_orphan_indices(body, valid_indices=set())
        assert "[1]" not in out
        assert "[2]" not in out

    def test_preserves_non_numeric_brackets(self):
        body = "메모: [note] 그리고 [1]."
        out = scrub_orphan_indices(body, valid_indices={1})
        assert "[note]" in out
        assert "[1]" in out


class TestMarkCitationsDropsOrphanKeys:
    """mark_citations는 candidate_sources에 없는 인덱스를 무시해야 하며,
    어떤 source도 환각된 키 때문에 잘못 인용 처리되지 않아야 한다."""

    def test_orphan_citation_key_does_not_attach_to_any_source(self):
        from types import SimpleNamespace

        from catchup.rag.nodes.utils import mark_citations

        sources = [
            SimpleNamespace(index=1, is_cited=False, citation_rationale=None),
            SimpleNamespace(index=2, is_cited=False, citation_rationale=None),
        ]
        citations = {"1": "valid", "14": "hallucinated"}
        out = mark_citations(sources, citations)
        assert len(out) == 2
        by_index = {s.index: s for s in out}
        assert by_index[1].is_cited is True
        assert by_index[1].citation_rationale == "valid"
        assert by_index[2].is_cited is False
