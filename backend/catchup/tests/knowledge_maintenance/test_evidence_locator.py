from __future__ import annotations

from catchup.knowledge_maintenance.domain.evidence import locate_excerpt


def test_locates_unique_statement_with_char_offsets() -> None:
    """본문에 정확히 한 번 나오는 문구는 문자 offset으로 위치가 잡힌다."""
    content = "고객: 결제가 안 돼요.\n상담원: 확인해 보겠습니다."
    statement = "결제가 안 돼요."

    locator = locate_excerpt(content, statement)

    assert locator is not None
    assert locator.kind == "char_offset"
    assert content[locator.start : locator.end] == statement


def test_returns_none_when_statement_is_absent() -> None:
    """본문에 없는 문구는 위치를 확정하지 않는다."""
    content = "고객: 결제가 안 돼요."

    assert locate_excerpt(content, "환불해 주세요.") is None


def test_returns_none_when_statement_is_ambiguous() -> None:
    """본문에 두 번 이상 나오는 문구는 어느 쪽인지 단정하지 않는다."""
    content = "고객: 결제가 안 돼요.\n상담원: 결제가 안 돼요, 맞으실까요?"

    assert locate_excerpt(content, "결제가 안 돼요") is None


def test_returns_none_when_content_is_missing() -> None:
    """본문이 없는 Observation에서는 위치를 잡을 수 없다."""
    assert locate_excerpt(None, "결제가 안 돼요.") is None
