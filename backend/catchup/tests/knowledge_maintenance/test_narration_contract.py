"""문서 단위 산문 응답의 결정론 검증기를 확인한다."""

from __future__ import annotations

from catchup.knowledge_maintenance.domain.narration_contract import (
    document_narration_violations,
)
from catchup.knowledge_maintenance.ports.narrator import BlockNarrationInput
from catchup.knowledge_maintenance.ports.narrator import DocumentNarrationRequest
from catchup.knowledge_maintenance.ports.narrator import SummaryNarrative


def _input(
    block_id=0,
    statements=("고객이 문의 3건을 남겼다.",),
    edges=(),
    heading="request_status",
):
    return BlockNarrationInput(
        block_id=block_id,
        block_kind="claim_section",
        heading=heading,
        topic_hint="collected (2026-08-07 관찰)",
        statements=statements,
        edges=edges,
        hints=(),
        variants=(),
    )


def _request(blocks, summary=None):
    return DocumentNarrationRequest(
        style_instruction="스타일",
        purpose_sentence="목적",
        summary=summary,
        blocks=blocks,
    )


def test_clean_narration_has_no_violation():
    found = document_narration_violations(
        _request((_input(),)),
        narratives={0: "문의 3건이 접수되었다."},
        summary=None,
    )
    assert found == ()


def test_missing_block_is_reported():
    found = document_narration_violations(
        _request((_input(),)), narratives={}, summary=None
    )
    assert any(v.block_id == 0 and "산문이 없다" in v.reason for v in found)


def test_unknown_block_id_is_reported():
    found = document_narration_violations(
        _request((_input(),)),
        narratives={0: "문의 3건이 접수되었다.", 7: "없는 블록."},
        summary=None,
    )
    assert any(v.block_id == 7 for v in found)


def test_number_outside_evidence_is_reported():
    found = document_narration_violations(
        _request((_input(),)),
        narratives={0: "문의 5건이 접수되었다."},
        summary=None,
    )
    assert any("5" in v.reason for v in found)


def test_observation_date_from_topic_hint_is_a_violation():
    """topic_hint의 날짜는 근거가 아니다. 산문이 되풀이하면 위반이다."""
    found = document_narration_violations(
        _request((_input(),)),
        narratives={0: "2026년에 문의 3건이 접수되었다."},
        summary=None,
    )
    assert any("2026" in v.reason for v in found)


def test_markdown_and_sentence_count_are_reported():
    long = "하나다. 둘이다. 셋이다. 넷이다."
    found = document_narration_violations(
        _request((_input(0), _input(1))),
        narratives={0: "**강조**다.", 1: long},
        summary=None,
    )
    assert any(v.block_id == 0 and "마크다운" in v.reason for v in found)
    assert any(v.block_id == 1 and "문장" in v.reason for v in found)


def test_decimal_is_not_counted_as_sentence_end():
    found = document_narration_violations(
        _request((_input(statements=("배율이 1.5배로 늘었다.",)),)),
        narratives={0: "배율이 1.5배로 늘었다."},
        summary=None,
    )
    assert found == ()


def test_summary_fields_are_checked():
    summary_input = _input(block_id=0)
    found = document_narration_violations(
        _request((), summary=summary_input),
        narratives={},
        summary=SummaryNarrative(
            one_line_summary="한 문장이다. 두 문장이다.",
            desired_outcome="",
            background="배경이다.",
        ),
    )
    assert any(v.block_id is None and "one_line_summary" in v.reason for v in found)
    assert any(v.block_id is None and "desired_outcome" in v.reason for v in found)


def test_missing_summary_is_reported():
    found = document_narration_violations(
        _request((), summary=_input()), narratives={}, summary=None
    )
    assert any(v.block_id is None for v in found)


def test_summary_may_state_a_number_from_a_relation_line():
    """머리말은 관계 간선에만 있는 숫자를 말해도 된다.

    요청자 이름에 숫자가 붙어 있으면 인용에는 없고 간선에만 있다.
    간선을 근거로 치지 않으면 참인 사실이 근거 없는 수로 반려된다.
    """
    summary_input = _input(
        block_id=-1,
        statements=("CSV 내보내기를 원한다.",),
        edges=("기능 요청 A → requested_by → 엘리 221",),
    )
    found = document_narration_violations(
        _request((), summary=summary_input),
        narratives={},
        summary=SummaryNarrative(
            one_line_summary="엘리 221이 CSV 내보내기를 원한다.",
            desired_outcome="요청 내역을 파일로 받는다.",
            background="지금은 손으로 옮겨 적는다.",
        ),
    )
    assert found == ()


def test_summary_number_outside_every_fact_is_reported():
    """인용에도 간선에도 없는 수는 머리말에서 여전히 위반이다."""
    summary_input = _input(
        block_id=-1,
        statements=("CSV 내보내기를 원한다.",),
        edges=("기능 요청 A → requested_by → 엘리 221",),
    )
    found = document_narration_violations(
        _request((), summary=summary_input),
        narratives={},
        summary=SummaryNarrative(
            one_line_summary="엘리 221이 CSV 내보내기 999건을 원한다.",
            desired_outcome="요청 내역을 파일로 받는다.",
            background="지금은 손으로 옮겨 적는다.",
        ),
    )
    assert any(v.block_id is None and "999" in v.reason for v in found)


def test_section_block_may_not_borrow_another_blocks_number():
    """섹션 블록은 제 근거만 쓴다. 다른 블록의 숫자를 쓰면 위반이다."""
    found = document_narration_violations(
        _request(
            (
                _input(0, statements=("고객이 문의 3건을 남겼다.",)),
                _input(1, statements=("담당이 정해지지 않았다.",)),
            )
        ),
        narratives={
            0: "문의 3건이 접수되었다.",
            1: "문의 3건의 담당이 정해지지 않았다.",
        },
        summary=None,
    )
    assert any(v.block_id == 1 and "3" in v.reason for v in found)
    assert not any(v.block_id == 0 for v in found)


def _two_section_request():
    """heading이 다른 섹션 두 개를 같은 근거로 묻는 요청을 만든다."""
    return _request(
        (
            _input(0, heading="request_status"),
            _input(1, heading="support_status"),
        )
    )


def test_same_narrative_in_two_blocks_is_reported_on_both():
    """서로 다른 섹션에 똑같은 산문이 실리면 양쪽 모두 위반이다."""
    found = document_narration_violations(
        _two_section_request(),
        narratives={
            0: "문의 3건이 접수되었다.",
            1: "문의 3건이 접수되었다.",
        },
        summary=None,
    )
    duplicated = [v for v in found if "같은 문장" in v.reason]
    assert {v.block_id for v in duplicated} == {0, 1}
    for violation in duplicated:
        assert "request_status" in violation.reason
        assert "support_status" in violation.reason


def test_duplicate_check_ignores_whitespace_differences():
    """줄바꿈과 겹친 공백만 다른 산문도 같은 문장으로 본다."""
    found = document_narration_violations(
        _two_section_request(),
        narratives={
            0: "문의 3건이  접수되었다.",
            1: "문의 3건이\n접수되었다.",
        },
        summary=None,
    )
    assert {v.block_id for v in found if "같은 문장" in v.reason} == {0, 1}


def test_similar_but_different_narratives_pass():
    """한 낱말이라도 다르면 중복으로 보지 않는다."""
    found = document_narration_violations(
        _two_section_request(),
        narratives={
            0: "문의 3건이 접수되었다.",
            1: "문의 3건이 아직 접수되었다.",
        },
        summary=None,
    )
    assert found == ()


def test_summary_field_matching_a_block_is_reported():
    """머리말 필드와 섹션 산문이 같으면 양쪽 모두 위반이다."""
    found = document_narration_violations(
        _request((_input(0),), summary=_input(block_id=-1)),
        narratives={0: "문의 3건이 접수되었다."},
        summary=SummaryNarrative(
            one_line_summary="고객이 문의를 남겼다.",
            desired_outcome="문의를 한자리에서 본다.",
            background="문의 3건이 접수되었다.",
        ),
    )
    duplicated = [v for v in found if "같은 문장" in v.reason]
    assert {v.block_id for v in duplicated} == {0, None}
    field = next(v for v in duplicated if v.block_id is None)
    assert field.reason.startswith("머리말 background:")
    assert "request_status" in field.reason


def test_summary_fields_matching_each_other_are_reported():
    """머리말 필드끼리 같아도 위반이다."""
    found = document_narration_violations(
        _request((), summary=_input(block_id=-1)),
        narratives={},
        summary=SummaryNarrative(
            one_line_summary="고객이 문의를 남겼다.",
            desired_outcome="문의 3건이 접수되었다.",
            background="문의 3건이 접수되었다.",
        ),
    )
    duplicated = [v for v in found if "같은 문장" in v.reason]
    assert len(duplicated) == 2
    assert all(v.block_id is None for v in duplicated)


def test_summary_may_not_state_the_topic_hint_date():
    """머리말도 topic_hint의 날짜는 쓸 수 없다. 간선이 늘어도 그대로다."""
    summary_input = _input(
        block_id=-1,
        statements=("CSV 내보내기를 원한다.",),
        edges=("기능 요청 A → requested_by → 엘리 221",),
    )
    found = document_narration_violations(
        _request((), summary=summary_input),
        narratives={},
        summary=SummaryNarrative(
            one_line_summary="2026년에 엘리 221이 CSV 내보내기를 원한다.",
            desired_outcome="요청 내역을 파일로 받는다.",
            background="지금은 손으로 옮겨 적는다.",
        ),
    )
    assert any(v.block_id is None and "2026" in v.reason for v in found)
