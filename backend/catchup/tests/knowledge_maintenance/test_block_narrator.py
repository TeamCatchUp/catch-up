"""문서 서술 어댑터가 무엇을 묻고 무엇을 실패로 다루는지 확인한다.

문서 하나의 산문을 한 번에 받는다. 받아 온 덩어리를 검증기에 걸어 위반이
있으면 위반 블록만 다시 묻고, 다시 물어도 남으면 실패로 끝낸다. 그 흐름과
프롬프트에 실리는 재료를 fake LLM으로 본다.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from structlog.testing import capture_logs

from catchup.knowledge_maintenance.adapters.llm import block_narrator
from catchup.knowledge_maintenance.adapters.llm.block_narrator import (
    DOCUMENT_PROMPT_VERSION,
)
from catchup.knowledge_maintenance.adapters.llm.block_narrator import (
    EXPLAIN_PROMPT_VERSION,
)
from catchup.knowledge_maintenance.adapters.llm.block_narrator import (
    RETRY_PROMPT_VERSION,
)
from catchup.knowledge_maintenance.adapters.llm.block_narrator import LlmBlockNarrator
from catchup.knowledge_maintenance.adapters.llm.block_narrator import _BlockNarrativeOut
from catchup.knowledge_maintenance.adapters.llm.block_narrator import (
    _DocumentNarrationContract,
)
from catchup.knowledge_maintenance.contracts.block_narration import ChangeReasonContract
from catchup.knowledge_maintenance.domain.narration_contract import BlockNarrationInput
from catchup.knowledge_maintenance.domain.narration_contract import (
    DocumentNarrationRequest,
)
from catchup.knowledge_maintenance.domain.narration_contract import block_fact_texts
from catchup.knowledge_maintenance.ports.narrator import ChangeExplanationRequest
from catchup.knowledge_maintenance.ports.narrator import NarrationError


class _FakeStructured:
    """구조화 출력을 흉내 내고 받은 프롬프트를 기록한다.

    응답을 여러 개 받아 부른 순서대로 돌려준다. 재시도가 있어 한 번의
    서술에서 호출이 두 번 일어나기 때문이다.
    """

    def __init__(self, responses: list[Any], error: Exception | None) -> None:
        self.responses = list(responses)
        self.error = error
        self.prompts: list[str] = []

    def invoke(self, rendered: str) -> Any:
        self.prompts.append(rendered)
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("예상보다 많이 불렀다")
        return self.responses.pop(0)


class _FakeLlm:
    """with_structured_output만 흉내 내는 모델이다.

    계약마다 다른 구조화 출력을 돌려준다. 어댑터가 문서 산문 계약과 변경
    이유 계약을 각각 따로 묶기 때문에, 하나로 뭉치면 어느 호출이 어느
    프롬프트를 받았는지 알 수 없다.
    """

    def __init__(
        self,
        document_responses: list[Any] | None = None,
        document_error: Exception | None = None,
        reason_response: Any = None,
        reason_error: Exception | None = None,
    ):
        self.document_structured = _FakeStructured(
            document_responses or [], document_error
        )
        self.reason_structured = _FakeStructured(
            [reason_response] if reason_response is not None else [], reason_error
        )
        self.document_kwargs: dict[str, Any] = {}
        self.reason_kwargs: dict[str, Any] = {}

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        if schema is ChangeReasonContract:
            self.reason_kwargs = {"schema": schema, **kwargs}
            return self.reason_structured
        self.document_kwargs = {"schema": schema, **kwargs}
        return self.document_structured


def _doc(
    narratives: tuple[tuple[int, str], ...] = (),
    *,
    one_line_summary: str | None = None,
    desired_outcome: str | None = None,
    background: str | None = None,
) -> dict[str, Any]:
    """정상 문서 산문 구조화 출력 응답을 만든다."""
    return {
        "parsed": _DocumentNarrationContract(
            narratives=[
                _BlockNarrativeOut(block_id=block_id, narrative=text)
                for block_id, text in narratives
            ],
            one_line_summary=one_line_summary,
            desired_outcome=desired_outcome,
            background=background,
        ),
        "parsing_error": None,
    }


def _block(
    block_id: int = 0,
    *,
    block_kind: str = "claim_section",
    heading: str = "request_status",
    topic_hint: str = "검토 중 (2026-08-15 관찰)",
    statements: tuple[str, ...] = ("상태는 검토 중이다",),
    edges: tuple[str, ...] = (),
    hints: tuple[str, ...] = (),
    variants: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> BlockNarrationInput:
    """블록 재료 하나를 만든다."""
    return BlockNarrationInput(
        block_id=block_id,
        block_kind=block_kind,
        heading=heading,
        topic_hint=topic_hint,
        statements=statements,
        edges=edges,
        hints=hints,
        variants=variants,
    )


def _request(
    blocks: tuple[BlockNarrationInput, ...] = (),
    summary: BlockNarrationInput | None = None,
) -> DocumentNarrationRequest:
    """문체·목적이 실린 문서 서술 요청을 만든다."""
    return DocumentNarrationRequest(
        style_instruction="보고서 요약 문단처럼 쓴다.",
        purpose_sentence="이 문서는 요구의 현황을 보는 데 쓴다.",
        summary=summary,
        blocks=blocks,
    )


def _summary_input() -> BlockNarrationInput:
    """머리말 재료를 만든다."""
    return _block(
        block_id=-1,
        block_kind="summary",
        heading="기능 요청: CSV",
        topic_hint="요청 세 건",
        statements=("A사가 CSV 내보내기를 원한다",),
    )


def test_clean_response_returns_all_narratives() -> None:
    """위반이 없으면 받아 온 산문을 그대로 돌려준다."""
    llm = _FakeLlm(
        [
            _doc(
                (
                    (0, "이 요구는 아직 검토 중이다."),
                    (1, "담당은 아직 정해지지 않았다."),
                )
            )
        ]
    )
    request = _request(
        (
            _block(0),
            _block(1, statements=("담당이 정해지지 않았다",)),
        )
    )

    result = LlmBlockNarrator(llm).narrate_document(request)

    assert result.narratives == {
        0: "이 요구는 아직 검토 중이다.",
        1: "담당은 아직 정해지지 않았다.",
    }
    assert result.summary is None
    assert len(llm.document_structured.prompts) == 1


def test_empty_request_makes_no_call() -> None:
    """물을 것이 없으면 모델을 부르지 않는다."""
    llm = _FakeLlm([])

    result = LlmBlockNarrator(llm).narrate_document(_request())

    assert result.narratives == {}
    assert result.summary is None
    assert llm.document_structured.prompts == []


def test_document_uses_function_calling_with_raw() -> None:
    """문서 산문도 어휘 수렴 어댑터와 같은 구조화 출력 관례를 쓴다."""
    llm = _FakeLlm([])

    LlmBlockNarrator(llm)

    assert llm.document_kwargs["schema"] is _DocumentNarrationContract
    assert llm.document_kwargs["method"] == "function_calling"
    assert llm.document_kwargs["include_raw"] is True


def test_prompt_carries_style_purpose_and_evidence() -> None:
    """문체·목적·인용이 프롬프트에 실제로 실린다."""
    llm = _FakeLlm([_doc(((0, "이 요구는 아직 검토 중이다."),))])

    LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    rendered = llm.document_structured.prompts[0]
    assert "보고서 요약 문단처럼 쓴다." in rendered
    assert "이 문서는 요구의 현황을 보는 데 쓴다." in rendered
    assert "상태는 검토 중이다" in rendered
    assert "request_status" in rendered
    assert "검토 중 (2026-08-15 관찰)" in rendered
    assert "Write in Korean." in rendered
    assert "## Block 0" in rendered


def test_prompt_puts_fixed_instructions_before_evidence() -> None:
    """고정 지시문이 앞에 서고 블록별 근거가 뒤에 선다.

    앞자리가 문서마다 같아야 프롬프트 캐시가 걸린다.
    """
    llm = _FakeLlm([_doc(((0, "이 요구는 아직 검토 중이다."),))])

    LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    rendered = llm.document_structured.prompts[0]
    assert (
        rendered.index("## Rules")
        < rendered.index("이 문서는 요구의 현황을 보는 데 쓴다.")
        < rendered.index("## Block 0")
    )


def test_prompt_keeps_relations_and_variants_apart() -> None:
    """관계 줄과 대조 후보가 블록별로 갈라져 실린다."""
    llm = _FakeLlm(
        [_doc(((0, "관계가 있다."), (1, "값이 갈린다.")))]
    )
    request = _request(
        (
            _block(
                0,
                block_kind="relation_section",
                heading="requested_by(out)",
                statements=(),
                edges=("기능 요청 A → requested_by → 팀원A",),
                hints=("커넥터 있어?",),
            ),
            _block(
                1,
                block_kind="contested",
                heading="rate_limit",
                statements=(),
                variants=(
                    ("60", ("한도는 육십이다",)),
                    ("120", ("한도는 백이십이다",)),
                ),
            ),
        )
    )

    LlmBlockNarrator(llm).narrate_document(request)

    rendered = llm.document_structured.prompts[0]
    assert "기능 요청 A → requested_by → 팀원A" in rendered
    assert "never infer another" in rendered
    assert "커넥터 있어?" in rendered
    assert "한도는 육십이다" in rendered
    assert "한도는 백이십이다" in rendered
    assert "do not judge which one is right." in rendered
    assert "The list may be partial" in rendered


def test_prompt_allows_relation_lines_as_evidence() -> None:
    """규칙 1이 관계 줄도 말해도 되는 근거로 친다.

    관계 절 블록은 인용이 없고 관계 줄만 있다. 규칙 1이 인용만 근거로
    치면 그 블록은 쓸 것이 없다고 읽힌다.
    """
    llm = _FakeLlm([_doc(((0, "관계가 있다."),))])
    request = _request(
        (
            _block(
                0,
                block_kind="relation_section",
                heading="requested_by(out)",
                statements=(),
                edges=("기능 요청 A → requested_by → 팀원A",),
            ),
        )
    )

    LlmBlockNarrator(llm).narrate_document(request)

    rendered = llm.document_structured.prompts[0]
    assert (
        "State only what that block's Evidence and relation lines already say."
        in rendered
    )


def test_prompt_forbids_the_candidate_observation_date() -> None:
    """대조 후보를 값으로만 부르게 하고 라벨의 관찰 날짜는 막는다.

    후보 라벨에 관찰 날짜가 찍혀 있어, 그대로 옮겨 쓰면 근거 밖 숫자로
    걸려 재시도가 난다.
    """
    llm = _FakeLlm([_doc(((0, "값이 갈린다."),))])
    request = _request(
        (
            _block(
                0,
                block_kind="contested",
                heading="rate_limit",
                statements=(),
                variants=(
                    ("60 (2026-08-07 관찰)", ("한도는 육십이다",)),
                    ("120 (2026-08-09 관찰)", ("한도는 백이십이다",)),
                ),
            ),
        )
    )

    LlmBlockNarrator(llm).narrate_document(request)

    rendered = llm.document_structured.prompts[0]
    assert "Name each candidate by its" in rendered
    assert (
        "never repeat the observation date printed in the candidate label."
        in rendered
    )


def test_prompt_carries_the_document_relations_in_the_opening() -> None:
    """머리말 재료의 관계 간선이 Opening 섹션에 사실로 실린다."""
    llm = _FakeLlm(
        [
            _doc(
                ((0, "이 요구는 아직 검토 중이다."),),
                one_line_summary="엘리 221이 CSV 내보내기를 원한다.",
                desired_outcome="요청 내역을 파일로 받는다.",
                background="지금은 손으로 옮겨 적는다.",
            )
        ]
    )
    summary = _block(
        block_id=-1,
        block_kind="summary",
        heading="기능 요청: CSV",
        topic_hint="요청 세 건",
        statements=("A사가 CSV 내보내기를 원한다",),
        edges=("기능 요청 A → requested_by → 엘리 221",),
    )

    LlmBlockNarrator(llm).narrate_document(_request((_block(0),), summary=summary))

    rendered = llm.document_structured.prompts[0]
    opening = _prompt_section(rendered, "## Opening (three fields)")
    assert "#### Relations (graph facts)" in opening
    assert "기능 요청 A → requested_by → 엘리 221" in opening


# 사실 텍스트를 싣는 소제목만 모은다. 이 목록에 없는 소제목 아래 줄은
# 사실이 아니다. `#### Wording hints (not facts)`는 표현 힌트라 빠지고,
# `#### Candidate: <본문>` 줄 자체도 빠진다. 후보 라벨에는 관찰 날짜가
# 찍혀 있어 프롬프트가 그 날짜를 옮겨 쓰지 말라고 시키기 때문이다.
# 소제목 앞의 `- heading (hint only)` 같은 줄도 소제목이 없으므로 빠진다.
_FACT_HEADINGS = ("### Evidence", "#### Relations (graph facts)")
_CANDIDATE_HEADING = "#### Candidate:"


def _prompt_section(rendered: str, start_heading: str) -> str:
    """렌더된 프롬프트에서 큰 제목 하나가 다스리는 구간만 잘라낸다.

    다음 `## `가 나오기 전까지가 그 구간이다. 고정 지시문에도 소제목
    이름이 글로 나오므로, 구간을 먼저 자르지 않으면 남의 글을 센다.
    """
    lines = rendered.split("\n")
    start = next(
        index for index, line in enumerate(lines) if line.startswith(start_heading)
    )
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _section_fact_digits(section: str) -> set[str]:
    """구간 안에서 사실 소제목이 다스리는 목록 줄의 숫자 열을 모은다."""
    digits: set[str] = set()
    heading = ""
    for line in section.split("\n"):
        if line.startswith("#"):
            heading = line
            continue
        if not line.startswith("- "):
            continue
        if heading in _FACT_HEADINGS or heading.startswith(_CANDIDATE_HEADING):
            digits.update(re.findall(r"\d+", line))
    return digits


def test_prompt_fact_text_matches_the_contract_for_a_block() -> None:
    """블록 섹션이 사실로 싣는 숫자와 검증기가 허용하는 숫자가 같다.

    템플릿이 사실로 싣는 필드와 검증기가 근거로 보는 필드가 어긋나면
    참인 문장이 위반으로 잡히거나 근거 없는 문장이 통과한다. 양쪽 집합이
    같은지 봐서 그 어긋남을 잡는다.
    """
    llm = _FakeLlm([_doc(((0, "문의 3건이 남았고 한도는 60이다."),))])
    block = _block(
        0,
        topic_hint="검토 중 (2026-08-15 관찰)",
        statements=("문의 3건이 남았다",),
        edges=("기능 요청 A → requested_by → 엘리 221",),
        hints=("담당자 7명이 붙었다",),
        variants=(("60", ("한도는 60이다",)),),
    )

    LlmBlockNarrator(llm).narrate_document(_request((block,)))

    section = _prompt_section(llm.document_structured.prompts[0], "## Block 0 ")
    contract_digits = set(re.findall(r"\d+", " ".join(block_fact_texts(block))))
    assert _section_fact_digits(section) == contract_digits
    assert contract_digits == {"3", "221", "60"}


def test_prompt_fact_text_matches_the_contract_for_the_opening() -> None:
    """머리말 섹션이 사실로 싣는 숫자와 검증기가 허용하는 숫자가 같다."""
    llm = _FakeLlm(
        [
            _doc(
                ((0, "이 요구는 아직 검토 중이다."),),
                one_line_summary="엘리 221이 CSV 내보내기를 원한다.",
                desired_outcome="요청 내역을 파일로 받는다.",
                background="지금은 손으로 옮겨 적는다.",
            )
        ]
    )
    summary = _block(
        block_id=-1,
        block_kind="summary",
        heading="기능 요청: CSV",
        topic_hint="요청 세 건 (2026-08-15 관찰)",
        statements=("A사가 CSV 내보내기를 원한다",),
        edges=("기능 요청 A → requested_by → 엘리 221",),
    )

    LlmBlockNarrator(llm).narrate_document(_request((_block(0),), summary=summary))

    section = _prompt_section(
        llm.document_structured.prompts[0], "## Opening (three fields)"
    )
    contract_digits = set(re.findall(r"\d+", " ".join(block_fact_texts(summary))))
    assert _section_fact_digits(section) == contract_digits
    assert contract_digits == {"221"}


def test_narrative_whitespace_is_stripped() -> None:
    """산문과 머리말 세 칸의 앞뒤 공백을 잘라서 담는다."""
    llm = _FakeLlm(
        [
            _doc(
                ((0, "\n  이 요구는 아직 검토 중이다.  \n"),),
                one_line_summary="  A사가 CSV 내보내기를 원한다.  ",
                desired_outcome="\n요청 내역을 파일로 받는다.\n",
                background="  지금은 손으로 옮겨 적는다.  ",
            )
        ]
    )
    request = _request((_block(0),), summary=_summary_input())

    result = LlmBlockNarrator(llm).narrate_document(request)

    assert result.narratives == {0: "이 요구는 아직 검토 중이다."}
    assert result.summary is not None
    assert result.summary.one_line_summary == "A사가 CSV 내보내기를 원한다."
    assert result.summary.desired_outcome == "요청 내역을 파일로 받는다."
    assert result.summary.background == "지금은 손으로 옮겨 적는다."


def test_violating_block_is_retried_with_feedback() -> None:
    """위반한 블록만 사유와 함께 다시 묻는다."""
    llm = _FakeLlm(
        [
            _doc(
                (
                    (0, "이 요구는 아직 검토 중이다."),
                    (1, "담당자 3명이 붙었다."),
                )
            ),
            _doc(((1, "담당은 아직 정해지지 않았다."),)),
        ]
    )
    request = _request(
        (
            _block(0),
            _block(1, heading="owner", statements=("담당이 정해지지 않았다",)),
        )
    )

    result = LlmBlockNarrator(llm).narrate_document(request)

    assert len(llm.document_structured.prompts) == 2
    retry_prompt = llm.document_structured.prompts[1]
    assert "담당이 정해지지 않았다" in retry_prompt
    assert "담당자 3명이 붙었다." in retry_prompt
    assert "3는 근거에 없는 수다" in retry_prompt
    assert "## Accepted paragraphs (read-only)" in retry_prompt
    assert "이 요구는 아직 검토 중이다." in retry_prompt
    assert "## Block 0" not in retry_prompt
    assert "## Block 1" in retry_prompt
    assert result.narratives == {
        0: "이 요구는 아직 검토 중이다.",
        1: "담당은 아직 정해지지 않았다.",
    }


def test_duplicate_narratives_across_blocks_are_retried() -> None:
    """두 섹션에 같은 산문이 오면 둘 다 다시 묻고 서로 다른 문장을 받는다."""
    llm = _FakeLlm(
        [
            _doc(((0, "문의가 접수되었다."), (1, "문의가 접수되었다."), (2, "담당이 없다."))),
            _doc(((0, "접수 상태는 완료다."), (1, "지원은 아직 시작되지 않았다."))),
        ]
    )
    request = _request(
        (
            _block(0, heading="request_status", statements=("문의가 접수되었다",)),
            _block(1, heading="support_status", statements=("지원이 시작되지 않았다",)),
            _block(2, heading="owner", statements=("담당이 없다",)),
        )
    )

    result = LlmBlockNarrator(llm).narrate_document(request)

    assert len(llm.document_structured.prompts) == 2
    retry_prompt = llm.document_structured.prompts[1]
    assert "## Block 0" in retry_prompt
    assert "## Block 1" in retry_prompt
    assert "## Block 2" not in retry_prompt
    assert "request_status와 support_status의 산문이 같은 문장이다" in retry_prompt
    assert result.narratives == {
        0: "접수 상태는 완료다.",
        1: "지원은 아직 시작되지 않았다.",
        2: "담당이 없다.",
    }


def test_unknown_block_id_is_dropped_without_retry() -> None:
    """묻지 않은 번호가 딸려 와도 다시 묻지 않고 그 산문만 버린다."""
    llm = _FakeLlm(
        [
            _doc(
                (
                    (0, "이 요구는 아직 검토 중이다."),
                    (7, "묻지 않은 블록의 문장이다."),
                )
            )
        ]
    )

    with capture_logs() as logs:
        result = LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    assert len(llm.document_structured.prompts) == 1
    assert result.narratives == {0: "이 요구는 아직 검토 중이다."}
    dropped = next(
        entry
        for entry in logs
        if entry["event"] == "document_narration_unknown_blocks"
    )
    assert dropped["unknown_block_ids"] == [7]


def test_retry_response_may_repeat_accepted_blocks() -> None:
    """재시도 응답에 통과한 블록이 섞여 와도 1차 산문을 지킨다."""
    llm = _FakeLlm(
        [
            _doc(
                (
                    (0, "이 요구는 아직 검토 중이다."),
                    (1, "담당자 3명이 붙었다."),
                )
            ),
            _doc(
                (
                    (0, "다시 써서 보낸 문장이다."),
                    (1, "담당은 아직 정해지지 않았다."),
                )
            ),
        ]
    )
    request = _request(
        (
            _block(0),
            _block(1, heading="owner", statements=("담당이 정해지지 않았다",)),
        )
    )

    result = LlmBlockNarrator(llm).narrate_document(request)

    assert result.narratives == {
        0: "이 요구는 아직 검토 중이다.",
        1: "담당은 아직 정해지지 않았다.",
    }


def test_retry_failure_raises_narration_error() -> None:
    """다시 물어도 위반이 남으면 실패로 끝낸다."""
    llm = _FakeLlm(
        [
            _doc(((0, "담당자 3명이 붙었다."),)),
            _doc(((0, "담당자 4명이 붙었다."),)),
        ]
    )

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    assert len(llm.document_structured.prompts) == 2


def test_duplicate_block_id_triggers_retry() -> None:
    """같은 블록에 산문이 두 번 오면 첫 값을 쓰지 않고 다시 묻는다."""
    llm = _FakeLlm(
        [
            _doc(((0, "먼저 온 문장이다."), (0, "나중에 온 문장이다."))),
            _doc(((0, "다시 쓴 문장이다."),)),
        ]
    )

    result = LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    assert len(llm.document_structured.prompts) == 2
    assert "같은 블록에 산문이 두 번 왔다" in llm.document_structured.prompts[1]
    assert result.narratives == {0: "다시 쓴 문장이다."}


def test_summary_fields_are_returned_when_requested() -> None:
    """머리말을 물었으면 세 칸을 그대로 돌려준다."""
    llm = _FakeLlm(
        [
            _doc(
                ((0, "이 요구는 아직 검토 중이다."),),
                one_line_summary="A사가 CSV 내보내기를 원한다.",
                desired_outcome="내려받은 파일을 바로 회계에 올릴 수 있게 된다.",
                background="지금은 화면을 손으로 옮겨 적고 있다.",
            )
        ]
    )
    request = _request((_block(0),), summary=_summary_input())

    result = LlmBlockNarrator(llm).narrate_document(request)

    assert result.summary is not None
    assert result.summary.one_line_summary == "A사가 CSV 내보내기를 원한다."
    assert (
        result.summary.desired_outcome
        == "내려받은 파일을 바로 회계에 올릴 수 있게 된다."
    )
    assert result.summary.background == "지금은 화면을 손으로 옮겨 적고 있다."
    rendered = llm.document_structured.prompts[0]
    assert "`one_line_summary`" in rendered
    assert "who wants to do what" in rendered
    assert "the final result the customer wants" in rendered
    assert "why the request came up" in rendered
    assert "A사가 CSV 내보내기를 원한다" in rendered


def test_unrequested_summary_is_dropped() -> None:
    """머리말을 묻지 않았으면 딸려 온 세 칸을 버린다."""
    llm = _FakeLlm(
        [
            _doc(
                ((0, "이 요구는 아직 검토 중이다."),),
                one_line_summary="묻지 않은 요약이다.",
                desired_outcome="묻지 않은 결과다.",
                background="묻지 않은 배경이다.",
            )
        ]
    )

    result = LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    assert result.summary is None
    assert len(llm.document_structured.prompts) == 1
    assert "## Opening (three fields)" not in llm.document_structured.prompts[0]


def test_missing_summary_is_retried() -> None:
    """머리말을 물었는데 오지 않으면 다시 묻는다."""
    llm = _FakeLlm(
        [
            _doc(((0, "이 요구는 아직 검토 중이다."),)),
            _doc(
                (),
                one_line_summary="A사가 CSV 내보내기를 원한다.",
                desired_outcome="내려받은 파일을 바로 회계에 올릴 수 있게 된다.",
                background="지금은 화면을 손으로 옮겨 적고 있다.",
            ),
        ]
    )
    request = _request((_block(0),), summary=_summary_input())

    result = LlmBlockNarrator(llm).narrate_document(request)

    assert len(llm.document_structured.prompts) == 2
    assert result.summary is not None
    assert result.narratives == {0: "이 요구는 아직 검토 중이다."}


def _unparsed(raw: str = '{"narratives": "[]"}') -> dict[str, Any]:
    """계약으로 옮기지 못한 구조화 출력 응답을 만든다."""
    return {
        "parsed": None,
        "parsing_error": ValueError("깨졌다"),
        "raw": raw,
    }


def test_parse_failure_is_retried_once() -> None:
    """1차가 파싱 실패면 같은 프롬프트로 한 번 더 묻는다."""
    llm = _FakeLlm([_unparsed(), _doc(((0, "이 요구는 아직 검토 중이다."),))])

    with capture_logs() as logs:
        result = LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    assert len(llm.document_structured.prompts) == 2
    assert llm.document_structured.prompts[0] == llm.document_structured.prompts[1]
    assert result.narratives == {0: "이 요구는 아직 검토 중이다."}
    retry = next(
        entry for entry in logs if entry["event"] == "document_narration_parse_retry"
    )
    assert retry["prompt_version"] == DOCUMENT_PROMPT_VERSION
    assert retry["reason"] == "contract_violation"


def test_contract_violation_is_an_error() -> None:
    """두 번 잇달아 파싱이 실패하면 실패로 알린다."""
    llm = _FakeLlm([_unparsed(), _unparsed()])

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    assert len(llm.document_structured.prompts) == 2


def test_retry_call_parse_failure_is_retried_once() -> None:
    """검증기 재시도 호출이 파싱 실패해도 한 번 더 묻는다."""
    llm = _FakeLlm(
        [
            _doc(((0, "담당자 3명이 붙었다."),)),
            _unparsed(),
            _doc(((0, "담당은 아직 정해지지 않았다."),)),
        ]
    )
    request = _request((_block(0, statements=("담당이 정해지지 않았다",)),))

    with capture_logs() as logs:
        result = LlmBlockNarrator(llm).narrate_document(request)

    assert len(llm.document_structured.prompts) == 3
    assert result.narratives == {0: "담당은 아직 정해지지 않았다."}
    retry = next(
        entry for entry in logs if entry["event"] == "document_narration_parse_retry"
    )
    assert retry["prompt_version"] == RETRY_PROMPT_VERSION


def _narration_template_sources() -> list[str]:
    """두 산문 템플릿 원문을 한 줄로 편 채로 읽는다.

    지시문이 폭에 맞춰 여러 줄로 접혀 있어, 줄바꿈과 들여쓰기를 공백
    하나로 눌러야 문장 그대로 찾을 수 있다.
    """
    return [
        " ".join(
            (block_narrator.prompt_loader.template_dir / path)
            .read_text(encoding="utf-8")
            .split()
        )
        for path in (
            block_narrator.DOCUMENT_TEMPLATE_PATH,
            block_narrator.RETRY_TEMPLATE_PATH,
        )
    ]


def test_templates_forbid_narratives_as_a_string() -> None:
    """두 산문 템플릿이 narratives를 문자열로 돌려주지 말라고 시킨다."""
    instruction = "Return narratives as a JSON array of objects, never as a string."

    for source in _narration_template_sources():
        assert instruction in source


def test_templates_ask_for_single_quotes_inside_narratives() -> None:
    """두 산문 템플릿이 산문 안의 인용을 작은따옴표로 쓰라고 시킨다.

    산문에 큰따옴표가 실리면 tool call JSON이 깨져 계약 파싱이 실패한다.
    """
    instruction = (
        "When quoting text inside a narrative, use single quotes ('), "
        'never double quotes (").'
    )

    for source in _narration_template_sources():
        assert instruction in source


def test_templates_forbid_repeating_a_sentence_across_blocks() -> None:
    """두 산문 템플릿이 같은 문장을 여러 블록에 되풀이하지 말라고 시킨다."""
    instruction = (
        "Write each block's paragraph from the angle its heading asks about. "
        "Blocks often share the same evidence, but never repeat the same "
        "sentence in two places. If the evidence adds nothing to that angle, "
        "write one short sentence."
    )

    for source in _narration_template_sources():
        assert instruction in source


def test_call_error_is_an_error() -> None:
    """호출 자체가 터져도 같은 예외로 감싼다."""
    llm = _FakeLlm(document_error=RuntimeError("연결 실패"))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))


def test_prompt_render_error_is_a_narration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """프롬프트 렌더링이 터져도 같은 예외로 감싼다."""

    def _boom(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("렌더링 실패")

    monkeypatch.setattr(block_narrator.prompt_loader, "get_prompt", _boom)
    llm = _FakeLlm([_doc(((0, "문장이다."),))])

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))


def test_logs_carry_prompt_version_and_no_content() -> None:
    """감사 로그에 판본과 개수만 남고 원문·산문은 남지 않는다."""
    llm = _FakeLlm([_doc(((0, "이 요구는 아직 검토 중이다."),))])

    with capture_logs() as logs:
        LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    events = [entry["event"] for entry in logs]
    assert "document_narration_started" in events
    assert "document_narration_completed" in events
    started = next(
        entry for entry in logs if entry["event"] == "document_narration_started"
    )
    assert started["prompt_version"] == DOCUMENT_PROMPT_VERSION
    assert started["block_count"] == 1
    dumped = str(logs)
    assert "상태는 검토 중이다" not in dumped
    assert "이 요구는 아직 검토 중이다." not in dumped


def test_retry_log_carries_reasons_without_prose() -> None:
    """재시도 로그에 위반 사유는 남고 받아 온 산문은 남지 않는다."""
    llm = _FakeLlm(
        [
            _doc(((0, "담당자 3명이 붙었다."),)),
            _doc(((0, "담당은 아직 정해지지 않았다."),)),
        ]
    )
    request = _request((_block(0, statements=("담당이 정해지지 않았다",)),))

    with capture_logs() as logs:
        LlmBlockNarrator(llm).narrate_document(request)

    retry = next(
        entry for entry in logs if entry["event"] == "document_narration_retry"
    )
    assert retry["violation_count"] == 1
    assert any("근거에 없는 수" in reason for reason in retry["reasons"])
    dumped = str(logs)
    assert "담당자 3명이 붙었다." not in dumped
    assert "담당은 아직 정해지지 않았다." not in dumped


def test_retry_log_counts_only_the_retried_blocks() -> None:
    """재시도 로그의 block_count가 다시 묻는 블록 수를 가리킨다."""
    llm = _FakeLlm(
        [
            _doc(((0, "담당은 아직 정해지지 않았다."), (1, "담당자 3명이 붙었다."))),
            _doc(((1, "상태는 아직 검토 중이다."),)),
        ]
    )
    request = _request(
        (
            _block(0, statements=("담당이 정해지지 않았다",)),
            _block(1),
        )
    )

    with capture_logs() as logs:
        LlmBlockNarrator(llm).narrate_document(request)

    started = [
        entry
        for entry in logs
        if entry["event"] == "document_narration_retry_started"
    ]
    assert len(started) == 1
    assert started[0]["prompt_version"] == RETRY_PROMPT_VERSION
    assert started[0]["block_count"] == 1


def test_failure_log_carries_no_prose() -> None:
    """실패 로그에도 받아 온 산문이 남지 않는다."""
    llm = _FakeLlm(
        [
            _doc(((0, "담당자 3명이 붙었다."),)),
            _doc(((0, "담당자 4명이 붙었다."),)),
        ]
    )

    with capture_logs() as logs:
        with pytest.raises(NarrationError):
            LlmBlockNarrator(llm).narrate_document(_request((_block(0),)))

    failed = next(
        entry for entry in logs if entry["event"] == "document_narration_failed"
    )
    assert failed["reason"] == "contract_violation"
    dumped = str(logs)
    assert "담당자 3명이 붙었다." not in dumped
    assert "담당자 4명이 붙었다." not in dumped


def _parsed_reason(text: str) -> dict[str, Any]:
    """정상 변경 이유 구조화 출력 응답을 만든다."""
    return {
        "parsed": ChangeReasonContract(reason=text),
        "parsing_error": None,
    }


def _change_request() -> ChangeExplanationRequest:
    """바뀐 블록 하나를 설명하는 요청을 만든다."""
    return ChangeExplanationRequest(
        heading="request_count",
        before_statements=("요청은 3회다",),
        after_statements=("요청은 4회다",),
        new_sources=("C사도 CSV 내보내기를 요청했다",),
        purpose_sentence="이 문서는 요구의 현황을 보는 데 쓴다.",
    )


def test_explain_change_returns_the_reason() -> None:
    """변경 이유를 그대로 돌려준다."""
    llm = _FakeLlm(
        reason_response=_parsed_reason("C사 요청이 더해져 횟수가 늘었다.")
    )

    reason = LlmBlockNarrator(llm).explain_change(_change_request())

    assert reason == "C사 요청이 더해져 횟수가 늘었다."


def test_explain_change_uses_function_calling_with_raw() -> None:
    """변경 이유도 같은 구조화 출력 관례를 쓴다."""
    llm = _FakeLlm(reason_response=_parsed_reason("이유다."))

    LlmBlockNarrator(llm)

    assert llm.reason_kwargs["schema"] is ChangeReasonContract
    assert llm.reason_kwargs["method"] == "function_calling"
    assert llm.reason_kwargs["include_raw"] is True


def test_explain_change_prompt_carries_before_after_and_sources() -> None:
    """이전·이후 문장과 새 인용이 프롬프트에 실린다."""
    llm = _FakeLlm(reason_response=_parsed_reason("이유다."))

    LlmBlockNarrator(llm).explain_change(_change_request())

    rendered = llm.reason_structured.prompts[0]
    assert "request_count" in rendered
    assert "요청은 3회다" in rendered
    assert "요청은 4회다" in rendered
    assert "C사도 CSV 내보내기를 요청했다" in rendered
    assert "이 문서는 요구의 현황을 보는 데 쓴다." in rendered
    assert "Write in Korean." in rendered
    assert "one sentence" in rendered.lower()


def test_explain_change_prompt_asks_for_the_polite_ending() -> None:
    """수정 이유 프롬프트는 존댓말 종결을 지시한다."""
    llm = _FakeLlm(reason_response=_parsed_reason("이유입니다."))

    LlmBlockNarrator(llm).explain_change(_change_request())

    assert "-습니다" in llm.reason_structured.prompts[0]


def test_explain_change_prompt_carries_no_style_instruction() -> None:
    """문서 문체 preset은 수정 이유 프롬프트에 실리지 않는다."""
    llm = _FakeLlm(reason_response=_parsed_reason("이유입니다."))

    LlmBlockNarrator(llm).explain_change(_change_request())

    assert "## Style" not in llm.reason_structured.prompts[0]


def test_explain_change_empty_reason_is_an_error() -> None:
    """빈 이유는 성공이 아니라 실패다."""
    llm = _FakeLlm(reason_response=_parsed_reason("   "))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).explain_change(_change_request())


def test_explain_change_contract_violation_is_an_error() -> None:
    """구조화 출력이 깨지면 실패로 알린다."""
    llm = _FakeLlm(
        reason_response={"parsed": None, "parsing_error": ValueError("깨졌다")}
    )

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).explain_change(_change_request())


def test_explain_change_call_error_is_an_error() -> None:
    """호출이 터져도 같은 예외로 감싼다."""
    llm = _FakeLlm(reason_error=RuntimeError("연결 실패"))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).explain_change(_change_request())


def test_explain_change_prompt_render_error_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """프롬프트 렌더링이 터져도 같은 예외로 감싼다."""

    def _boom(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("렌더링 실패")

    monkeypatch.setattr(block_narrator.prompt_loader, "get_prompt", _boom)
    llm = _FakeLlm(reason_response=_parsed_reason("이유다."))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).explain_change(_change_request())


def test_explain_change_logs_carry_counts_and_no_content() -> None:
    """감사 로그에 판본과 개수만 남고 원문·이유는 남지 않는다."""
    llm = _FakeLlm(
        reason_response=_parsed_reason("C사 요청이 더해져 횟수가 늘었다.")
    )

    with capture_logs() as logs:
        LlmBlockNarrator(llm).explain_change(_change_request())

    events = [entry["event"] for entry in logs]
    assert "block_change_explanation_started" in events
    assert "block_change_explanation_completed" in events
    started = next(
        entry
        for entry in logs
        if entry["event"] == "block_change_explanation_started"
    )
    assert started["prompt_version"] == EXPLAIN_PROMPT_VERSION
    assert started["before_count"] == 1
    assert started["after_count"] == 1
    assert started["new_source_count"] == 1
    dumped = str(logs)
    assert "요청은 3회다" not in dumped
    assert "C사도 CSV 내보내기를 요청했다" not in dumped
    assert "C사 요청이 더해져 횟수가 늘었다." not in dumped


def test_explain_change_failure_logs_no_exception_message() -> None:
    """실패 로그에 예외 메시지와 원문이 남지 않는다."""
    llm = _FakeLlm(reason_error=RuntimeError("요청 거절: 요청은 3회다"))

    with capture_logs() as logs:
        with pytest.raises(NarrationError):
            LlmBlockNarrator(llm).explain_change(_change_request())

    dumped = str(logs)
    assert "요청은 3회다" not in dumped
    assert "요청 거절" not in dumped
    failed = next(
        entry
        for entry in logs
        if entry["event"] == "block_change_explanation_failed"
    )
    assert failed["error_type"] == "RuntimeError"
    assert failed["reason"] == "llm_call_error"
