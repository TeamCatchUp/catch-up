"""문서 단위 산문의 요청·응답 모양과 그것이 지켜야 할 규칙을 정한다.

문서 하나의 산문을 한 번에 받으면 응답은 여러 블록의 문장이 섞인 덩어리가
된다. 그 덩어리를 그대로 믿고 문서에 넣을 수는 없으므로, 블록마다 따로
받던 시절에 걸어 두었던 규칙을 여기서 다시 건다. 빠진 블록, 요청에 없던
블록, 마크다운 표기, 너무 긴 문단, 근거에 없는 숫자, 서로 다른 자리에
똑같이 실린 산문을 찾는다.

검사는 전부 결정론이다. 모델을 다시 부르지 않고 문자열만 보므로 같은
응답이면 언제나 같은 위반 목록이 나온다. 위반의 reason은 사람이 읽는
설명인 동시에 다시 물을 때 모델에게 그대로 건네는 지적 문장이다.

topic_hint와 관찰 시각은 근거가 아니다. 주제를 알리는 힌트일 뿐이라
거기 실린 숫자를 산문이 되풀이하면 위반으로 잡는다.

요청과 응답을 담는 자료형도 여기에 둔다. 검사기가 그 모양을 알아야 하는데,
포트에 두고 여기서 가져오면 도메인이 포트를 향하게 된다. 포트가 도메인을
가져다 쓰는 것이 제 방향이라 자료형을 이쪽에 두고 포트가 가져간다.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

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
class BlockNarrationInput:
    """문서 서술 요청에 실리는 블록 하나의 재료를 담는다.

    문체 지시와 문서 목적은 담지 않는다. 그 둘은 문서 전체에 한 번만
    실리므로 DocumentNarrationRequest가 가진다.

    Attributes:
        block_id: 요청 안에서의 위치 번호를 담는다. 응답은 이 번호로
            산문을 돌려주므로, 어느 산문이 어느 블록의 것인지 이 번호로만
            정해진다.
        block_kind: 블록 종류를 나타낸다.
        heading: 블록 제목을 담는다. 무엇에 관한 블록인지 알리는 힌트다.
        topic_hint: 컴파일이 만든 본문을 담는다. 색인용 라벨에서 온
            문장이라 근거가 아니라 주제 힌트다.
        statements: 검증된 인용 원문을 담는다.
        edges: 관계 간선 줄을 담는다. 관계 절 블록은 제 간선을 담고,
            머리말 재료는 문서 전체의 간선을 담는다. 나머지 블록에서는
            비어 있다.
        hints: 관계에 붙은 원문 유래 문장을 담는다. 사실 입력이 아니라
            표현 힌트다.
        variants: 대조 후보를 (후보 본문, 그 후보의 인용들)로 담는다.
    """

    block_id: int
    block_kind: str
    heading: str
    topic_hint: str
    statements: tuple[str, ...]
    edges: tuple[str, ...]
    hints: tuple[str, ...]
    variants: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True, slots=True)
class DocumentNarrationRequest:
    """문서 하나의 산문을 한 번에 받아 오는 데 필요한 재료를 담는다.

    블록마다 따로 묻지 않고 문서 단위로 한 번만 묻는다. 문체 지시와 문서
    목적이 블록 수만큼 되풀이되지 않고, 같은 문서의 블록들이 서로의 문장을
    보고 쓸 수 있다.

    Attributes:
        style_instruction: 어떤 문체로 쓸지 알리는 지시 한 문단이다.
        purpose_sentence: 이 문서가 무엇에 쓰이는지 알리는 한 줄이다.
        summary: 머리말 세 칸을 쓰는 데 필요한 재료를 담는다. 머리말이
            필요 없으면 None이다. 머리말의 근거는 문서 전체의 검증된
            인용과 문서 전체의 관계 간선이다.
        blocks: 산문이 필요한 섹션 블록만 담는다. 앞 버전의 산문을 그대로
            쓰는 블록은 담지 않는다.
    """

    style_instruction: str
    purpose_sentence: str
    summary: BlockNarrationInput | None
    blocks: tuple[BlockNarrationInput, ...]


@dataclass(frozen=True, slots=True)
class SummaryNarrative:
    """문서 머리말을 이루는 세 칸을 담는다.

    머리말은 한 덩어리 문장이 아니라 정해진 세 칸으로 읽힌다. 자유
    문자열 하나로 돌려주면 어느 문장이 어느 칸인지 밖에서 알 수 없어,
    받는 자리에서 칸을 갈라 둔다.

    Attributes:
        one_line_summary: 누가 무엇을 하고 싶어 하는지 한 문장으로 담는다.
            이 문장만 읽어도 요구가 무엇인지 알 수 있어야 한다.
        desired_outcome: 고객이 얻고자 하는 최종 결과를 담는다. 무엇을
            어떻게 만들지가 아니라 결과만 적는다.
        background: 요청이 나온 이유와 지금 어떻게 일하고 있는지를 담는다.
            고객이 말한 사실만 적는다.
    """

    one_line_summary: str
    desired_outcome: str
    background: str


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
        찾은 위반을 담은 튜플이다. 요청한 블록의 위반이 요청 순서대로
        먼저 오고, 요청에 없던 블록 번호의 위반이 번호 순으로 뒤에 붙고,
        머리말 위반이 그다음에 오고, 여러 자리에 걸친 중복 위반이 맨 끝에
        온다.
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
    violations.extend(_duplicate_violations(request, narratives, summary))
    return tuple(violations)


def _duplicate_violations(
    request: DocumentNarrationRequest,
    narratives: Mapping[int, str],
    summary: SummaryNarrative | None,
) -> list[NarrationViolation]:
    """서로 다른 자리에 똑같은 산문이 실렸는지 본다.

    한 발화가 여러 predicate의 인용이 되면 블록들의 근거가 겹친다. 그때
    모델이 같은 문장을 여러 섹션에 그대로 붙여 놓는 일이 실측에서 나왔다.
    읽는 사람에게는 같은 말을 되풀이하는 문서로 보이므로 위반으로 잡는다.

    비교는 문자열 동일성만 본다. 공백을 고른 뒤 완전히 같을 때만 위반이다.
    비슷한 문장은 건드리지 않는다. 어디까지가 비슷한 것인지 정하려면
    문장을 재는 기준이 필요한데, 그 기준이 흔들리면 제대로 쓴 문장까지
    걸린다. 겹치는 근거를 두 관점에서 쓴 문장은 원래 닮게 마련이다.

    위반은 겹친 자리 모두에 단다. 어느 쪽을 남기고 어느 쪽을 고칠지는
    검사기가 정하지 않는다. 각 heading이 무엇을 묻는지 아는 쪽은 모델이라,
    고르는 일은 다시 묻는 자리에 넘긴다.

    비교 대상에는 머리말 세 칸도 넣는다. 머리말 background와 어떤 섹션의
    산문이 같은 문장이던 사례가 실측에 있다. 필드끼리 같아도 위반이다.

    Args:
        request: 무엇을 물었는지 알아야 요청한 블록만 셀 수 있어 받는다.
        narratives: 블록 번호를 산문에 짝지어 받는다.
        summary: 받아 온 머리말 세 칸을 받는다. 없으면 None이다.

    Returns:
        겹친 자리마다 하나씩 만든 위반을 담은 목록이다. 요청 순서대로
        블록의 위반이 먼저 오고 머리말 필드의 위반이 뒤에 온다.
    """
    entries: list[tuple[int | None, str, str]] = []
    for block in request.blocks:
        text = narratives.get(block.block_id)
        if text is not None and text.strip():
            entries.append((block.block_id, block.heading, _normalized(text)))
    if request.summary is not None and summary is not None:
        for name in ("one_line_summary", "desired_outcome", "background"):
            text = getattr(summary, name)
            if text.strip():
                entries.append((None, f"머리말 {name}", _normalized(text)))

    groups: dict[str, list[tuple[int | None, str]]] = {}
    for block_id, label, key in entries:
        groups.setdefault(key, []).append((block_id, label))

    violations: list[NarrationViolation] = []
    for block_id, label, key in entries:
        members = groups[key]
        if len(members) < 2:
            continue
        reason = (
            f"{'와 '.join(member_label for _id, member_label in members)}의 산문이"
            " 같은 문장이다. 각 heading이 묻는 관점으로 다르게 써라"
        )
        if block_id is None:
            reason = f"{label}: {reason}"
        violations.append(NarrationViolation(block_id=block_id, reason=reason))
    return violations


def _normalized(text: str) -> str:
    """산문을 견줄 수 있게 공백을 고른다.

    앞뒤 공백을 자르고 이어진 공백과 줄바꿈을 하나로 눌러 준다. 같은
    문장을 옮겨 적으면서 줄바꿈만 달라진 경우를 다른 문장으로 보지
    않기 위해서다.
    """
    return " ".join(text.split())


def _summary_violations(
    request_summary: BlockNarrationInput | None,
    summary: SummaryNarrative | None,
) -> list[NarrationViolation]:
    """머리말 세 칸을 검사한다.

    한 줄 요약만 한 문장으로 묶는다. 나머지 두 칸은 본문 블록과 같은
    1~3문장이다.

    숫자 근거는 섹션 블록과 같은 자리에서 고른다. 머리말 재료에는 인용뿐
    아니라 문서 전체의 관계 간선도 실리므로, 인용만 근거로 치면 간선에만
    있는 요청자 이름 같은 사실이 근거 없는 수로 잡힌다.
    """
    if request_summary is None:
        return []
    if summary is None:
        return [
            NarrationViolation(
                block_id=None, reason="머리말이 없다. 머리말 세 칸을 모두 써라"
            )
        ]

    evidence_digits = _block_evidence_digits(request_summary)
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


def block_fact_texts(block: BlockNarrationInput) -> tuple[str, ...]:
    """블록이 사실로 쓸 수 있는 텍스트를 프롬프트에 실리는 차례대로 모은다.

    프롬프트가 그 블록 섹션에 사실로 싣는 텍스트와 이 함수의 반환이 같아야
    한다. 어긋나면 모델이 본 사실이 위반으로 잡히거나(오탐) 못 본 것이
    허용된다(미탐). 그래서 근거를 쓰는 자리마다 따로 고르지 않고 이 함수
    하나로 모으고, 템플릿과 어긋나지 않는지는 회귀 테스트로 잠근다.

    사실 텍스트는 검증된 인용, 관계 간선 줄, 대조 후보의 인용이다. 대조
    블록은 후보마다 인용이 갈려 있어 후보의 인용까지 함께 모은다.
    topic_hint와 hints는 색인용 라벨과 표현 힌트라 넣지 않는다. 대조 후보의
    본문도 넣지 않는다. 후보 라벨에는 관찰 날짜가 찍혀 있고 프롬프트가 그
    날짜를 옮겨 쓰지 말라고 시키므로, 라벨을 사실로 치면 막으려던 날짜가
    도로 허용된다.

    Args:
        block: 사실 텍스트를 모을 블록 재료를 받는다.

    Returns:
        사실 텍스트를 프롬프트 차례대로 담은 튜플이다.
    """
    texts = [*block.statements, *block.edges]
    for _variant_body, quotes in block.variants:
        texts.extend(quotes)
    return tuple(texts)


def _block_evidence_digits(block: BlockNarrationInput) -> set[str]:
    """블록이 사실로 쓸 수 있는 글에서 숫자 열을 모은다."""
    return _digit_runs(" ".join(block_fact_texts(block)))


def _digit_runs(text: str) -> set[str]:
    """글에 나오는 숫자 열을 모은다.

    자릿수를 붙인 채로 본다. 소수점이나 하이픈은 경계로 삼으므로
    "1.5"는 "1"과 "5" 두 개로 갈린다. 근거에 "1.5"가 있으면 산문의
    "1.5"도 통과한다.
    """
    return set(_DIGIT_RUN.findall(text))
