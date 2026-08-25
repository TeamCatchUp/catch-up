"""문서 단위 산문 응답의 결정론 검증기를 확인한다."""

from __future__ import annotations

from catchup.knowledge_maintenance.domain.narration_contract import (
    document_narration_violations,
)
from catchup.knowledge_maintenance.ports.narrator import BlockNarrationInput
from catchup.knowledge_maintenance.ports.narrator import DocumentNarrationRequest
from catchup.knowledge_maintenance.ports.narrator import SummaryNarrative


def _input(block_id=0, statements=("고객이 문의 3건을 남겼다.",), edges=()):
    return BlockNarrationInput(
        block_id=block_id,
        block_kind="claim_section",
        heading="request_status",
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
