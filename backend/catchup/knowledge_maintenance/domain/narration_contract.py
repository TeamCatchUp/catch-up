"""문서 단위로 받아 온 산문이 지켜야 할 규칙을 검사한다.

문서 하나의 산문을 한 번에 받으면 응답은 여러 블록의 문장이 섞인 덩어리가
된다. 그 덩어리를 그대로 믿고 문서에 넣을 수는 없으므로, 블록마다 따로
받던 시절에 걸어 두었던 규칙을 여기서 다시 건다. 빠진 블록, 요청에 없던
블록, 마크다운 표기, 너무 긴 문단, 근거에 없는 숫자를 찾는다.

검사는 전부 결정론이다. 모델을 다시 부르지 않고 문자열만 보므로 같은
응답이면 언제나 같은 위반 목록이 나온다. 위반의 reason은 사람이 읽는
설명인 동시에 다시 물을 때 모델에게 그대로 건네는 지적 문장이다.

topic_hint와 관찰 시각은 근거가 아니다. 주제를 알리는 힌트일 뿐이라
거기 실린 숫자를 산문이 되풀이하면 위반으로 잡는다.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from catchup.knowledge_maintenance.ports.narrator import BlockNarrationInput
from catchup.knowledge_maintenance.ports.narrator import DocumentNarrationRequest
from catchup.knowledge_maintenance.ports.narrator import SummaryNarrative

_DIGIT_RUN = re.compile(r"\d+")
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_MAX_BLOCK_SENTENCES = 3

_MARKDOWN_MARKS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("**", re.compile(r"\*\*")),
    ("```", re.compile(r"```")),
    ("줄 시작의 #", re.compile(r"^#", re.MULTILINE)),
    ("줄 시작의 '- '", re.compile(r"^- ", re.MULTILINE)),
    ("줄 시작의 '* '", re.compile(r"^\* ", re.MULTILINE)),
    ("줄 시작의 번호 매기기", re.compile(r"^\d+\. ", re.MULTILINE)),
)


@dataclass(frozen=True, slots=True)
class NarrationViolation:
    """검증기가 찾은 위반 하나를 담는다.

    Attributes:
        block_id: 위반이 난 블록의 위치 번호를 담는다. None이면 머리말
            필드의 위반이고, 어느 칸인지는 reason이 이름으로 밝힌다.
        reason: 무엇이 잘못됐는지 한 문장으로 담는다. 다시 물을 때 이
            문장을 그대로 모델에게 건넨다.
    """

    block_id: int | None
    reason: str


def document_narration_violations(
    request: DocumentNarrationRequest,
    *,
    narratives: Mapping[int, str],
    summary: SummaryNarrative | None,
) -> tuple[NarrationViolation, ...]:
    """문서 산문 응답이 요청과 규칙에 맞는지 보고 위반 목록을 돌려준다.

    빈 튜플이면 응답을 그대로 써도 된다는 뜻이다. 요청에 머리말 재료가
    없는데 머리말이 딸려 오는 경우는 위반으로 세지 않는다. 버리면 그만인
    값이고, 버리는 일은 어댑터가 한다.

    Args:
        request: 모델에게 보냈던 요청을 받는다. 무엇을 물었는지 알아야
            빠진 블록과 요청에 없던 블록을 가릴 수 있다.
        narratives: 블록 번호를 산문에 짝지어 받는다.
        summary: 받아 온 머리말 세 칸을 받는다. 없으면 None이다.

    Returns:
        찾은 위반을 블록 번호 순으로 담은 튜플이다.
    """
    violations: list[NarrationViolation] = []
    requested_ids = {block.block_id for block in request.blocks}

    for block in request.blocks:
        text = narratives.get(block.block_id)
        if text is None:
            violations.append(
                NarrationViolation(
                    block_id=block.block_id,
                    reason=f"{block.block_id}번 블록의 산문이 없다. 빠뜨리지 말고 써라",
                )
            )
            continue
        violations.extend(
            _prose_violations(
                block.block_id,
                text,
                _block_evidence_digits(block),
                max_sentences=_MAX_BLOCK_SENTENCES,
            )
        )

    for unknown_id in sorted(set(narratives) - requested_ids):
        violations.append(
            NarrationViolation(
                block_id=unknown_id,
                reason=f"{unknown_id}번 블록은 요청에 없다. 요청한 번호에만 답하라",
            )
        )

    violations.extend(_summary_violations(request.summary, summary))
    return tuple(violations)


def _summary_violations(
    request_summary: BlockNarrationInput | None,
    summary: SummaryNarrative | None,
) -> list[NarrationViolation]:
    """머리말 세 칸을 검사한다.

    한 줄 요약만 한 문장으로 묶는다. 나머지 두 칸은 본문 블록과 같은
    1~3문장이다.
    """
    if request_summary is None:
        return []
    if summary is None:
        return [
            NarrationViolation(
                block_id=None, reason="머리말이 없다. 머리말 세 칸을 모두 써라"
            )
        ]

    evidence_digits = _digit_runs(" ".join(request_summary.statements))
    fields = (
        ("one_line_summary", summary.one_line_summary, 1),
        ("desired_outcome", summary.desired_outcome, _MAX_BLOCK_SENTENCES),
        ("background", summary.background, _MAX_BLOCK_SENTENCES),
    )

    violations: list[NarrationViolation] = []
    for name, text, max_sentences in fields:
        for violation in _prose_violations(
            None, text, evidence_digits, max_sentences=max_sentences
        ):
            violations.append(
                NarrationViolation(
                    block_id=None, reason=f"머리말 {name}: {violation.reason}"
                )
            )
    return violations


def _prose_violations(
    block_id: int | None,
    text: str,
    evidence_digits: set[str],
    *,
    max_sentences: int,
) -> list[NarrationViolation]:
    """산문 한 덩어리가 표기·길이·숫자 규칙을 지키는지 본다.

    비어 있으면 나머지는 보지 않는다. 빈 문장에 대고 문장 수와 숫자를
    따져 봐야 지적이 늘기만 하고 고칠 거리는 하나다.
    """
    if not text.strip():
        return [
            NarrationViolation(block_id=block_id, reason="산문이 비어 있다. 문장을 써라")
        ]

    violations: list[NarrationViolation] = []

    marks = [name for name, pattern in _MARKDOWN_MARKS if pattern.search(text)]
    if marks:
        violations.append(
            NarrationViolation(
                block_id=block_id,
                reason=f"마크다운 표기를 쓰지 마라: {', '.join(marks)}",
            )
        )

    sentences = len(_SENTENCE_END.findall(text))
    expected = "1문장" if max_sentences == 1 else f"1~{max_sentences}문장"
    if sentences == 0:
        violations.append(
            NarrationViolation(
                block_id=block_id,
                reason=f"문장이 마침표로 끝나지 않는다. {expected}으로 써라",
            )
        )
    elif sentences > max_sentences:
        violations.append(
            NarrationViolation(
                block_id=block_id,
                reason=f"문장이 {sentences}개다. {expected}으로 줄여라",
            )
        )

    for run in sorted(_digit_runs(text) - evidence_digits):
        violations.append(
            NarrationViolation(
                block_id=block_id, reason=f"{run}는 근거에 없는 수다. 빼거나 고쳐라"
            )
        )

    return violations


def _block_evidence_digits(block: BlockNarrationInput) -> set[str]:
    """블록이 사실로 쓸 수 있는 글에서 숫자 열을 모은다.

    사실 입력은 인용과 간선 줄뿐이다. 대조 블록은 후보마다 인용이 갈려
    있어 후보의 인용까지 함께 본다. topic_hint와 hints는 넣지 않는다.
    """
    parts = [*block.statements, *block.edges]
    for _variant_text, quotes in block.variants:
        parts.extend(quotes)
    return _digit_runs(" ".join(parts))


def _digit_runs(text: str) -> set[str]:
    """글에 나오는 숫자 열을 모은다.

    자릿수를 붙인 채로 본다. 소수점이나 하이픈은 경계로 삼으므로
    "1.5"는 "1"과 "5" 두 개로 갈린다. 근거에 "1.5"가 있으면 산문의
    "1.5"도 통과한다.
    """
    return set(_DIGIT_RUN.findall(text))
