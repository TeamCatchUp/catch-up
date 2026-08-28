"""LLM에게 문서 산문을 물어보는 어댑터를 정의한다."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.knowledge_maintenance.adapters.llm.prompt_versioning import (
    versioned_prompt,
)
from catchup.knowledge_maintenance.adapters.llm.retry import retry_llm_call
from catchup.knowledge_maintenance.contracts.block_narration import ChangeReasonContract
from catchup.knowledge_maintenance.domain.narration_contract import BlockNarrationInput
from catchup.knowledge_maintenance.domain.narration_contract import (
    DocumentNarrationRequest,
)
from catchup.knowledge_maintenance.domain.narration_contract import NarrationViolation
from catchup.knowledge_maintenance.domain.narration_contract import SummaryNarrative
from catchup.knowledge_maintenance.domain.narration_contract import (
    document_narration_violations,
)
from catchup.knowledge_maintenance.ports.narrator import ChangeExplanationRequest
from catchup.knowledge_maintenance.ports.narrator import DocumentNarration
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.observability.logging import get_logger
from catchup.prompts.loader import prompt_loader

DOCUMENT_TEMPLATE_PATH = "knowledge_maintenance/narrate_document.j2"
DOCUMENT_PROMPT_VERSION = versioned_prompt(DOCUMENT_TEMPLATE_PATH)
RETRY_TEMPLATE_PATH = "knowledge_maintenance/narrate_document_retry.j2"
RETRY_PROMPT_VERSION = versioned_prompt(RETRY_TEMPLATE_PATH)
EXPLAIN_TEMPLATE_PATH = "knowledge_maintenance/explain_block_change.j2"
EXPLAIN_PROMPT_VERSION = versioned_prompt(EXPLAIN_TEMPLATE_PATH)

_SUMMARY_FIELDS = ("one_line_summary", "desired_outcome", "background")

logger = get_logger(__name__)


class _ContractParseError(NarrationError):
    """구조화 출력을 계약 객체로 옮기지 못했을 때만 던진다.

    호출은 성공했는데 돌아온 값이 계약 모양이 아닌 경우다. 모델이
    narratives를 목록 대신 문자열로 돌려주는 것처럼, 같은 프롬프트로 다시
    물으면 풀릴 때가 있다. 부르는 쪽이 이 부류만 골라 다시 부를 수 있도록
    NarrationError 아래에 따로 둔다. 밖에서 보면 여전히 NarrationError라
    이 예외를 모르는 호출부의 동작은 바뀌지 않는다.
    """


class _BlockNarrativeOut(BaseModel):
    """블록 하나에 붙일 산문을 블록 번호와 함께 담는다.

    Attributes:
        block_id: 어느 블록의 산문인지 알리는 요청 안의 위치 번호를 담는다.
        narrative: 사람이 읽을 산문 본문을 담는다.
    """

    model_config = ConfigDict(frozen=True)

    block_id: int
    narrative: str


class _DocumentNarrationContract(BaseModel):
    """문서 하나의 산문 응답을 담는다.

    머리말 세 칸을 선택 항목으로 둔다. 머리말이 필요 없는 문서에도 같은
    계약을 쓰기 때문이다. 묻지 않았는데 딸려 온 값은 어댑터가 버린다.

    Attributes:
        narratives: 블록 번호와 산문의 짝을 담는다.
        one_line_summary: 누가 무엇을 하고 싶어 하는지 한 문장을 담는다.
        desired_outcome: 고객이 얻고자 하는 최종 결과를 담는다.
        background: 요청이 나온 이유와 지금의 업무 방식을 담는다.
    """

    model_config = ConfigDict(frozen=True)

    narratives: list[_BlockNarrativeOut] = Field(default_factory=list)
    one_line_summary: str | None = None
    desired_outcome: str | None = None
    background: str | None = None


class LlmBlockNarrator:
    """문서 재료를 주고 블록별 산문을 구조화 출력으로 받는다.

    한 문서를 한 번에 묻는다. 받아 온 값은 결정론 검사기에 걸고, 위반이
    있으면 위반 블록만 한 번 다시 묻는다. 다시 물어도 남으면 예외로
    끝낸다. 산문이 반쪽인 문서를 검수자에게 올리지 않는 것이 결정이다.

    재시도를 한 번만 둔다. 실패한 노드는 이번 실행에서 접히고 다음 실행이
    같은 자리를 다시 컴파일하므로, 한 호출 안에서 더 조를 이유가 없다.

    재시도 층이 둘이라는 점에 주의한다. 위의 검증기 위반 재시도는 위반
    블록만 사유와 함께 다시 묻는 층이고, 그 아래에 구조화 출력 파싱 실패를
    같은 프롬프트로 다시 묻는 층이 따로 있다. 아래층은 본 호출과 검증기
    재시도 호출에 각각 한 번씩 붙는다.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._document_structured = llm.with_structured_output(
            _DocumentNarrationContract,
            method="function_calling",
            include_raw=True,
        )
        self._reason_structured = llm.with_structured_output(
            ChangeReasonContract,
            method="function_calling",
            include_raw=True,
        )

    def narrate_document(
        self, request: DocumentNarrationRequest
    ) -> DocumentNarration:
        """문서 하나의 산문을 한 번에 받는다.

        무엇을 몇 개 물었고 무엇이 위반이었는지만 로그에 남긴다. 인용
        원문과 받아 온 산문은 싣지 않는다. 원문은 상담·대화 조각이고 감사
        로그는 오래 남기 때문이다. 위반 사유는 검사기가 만든 요약 문장이라
        산문 본문이 실리지 않는다.

        묻지 않은 블록 번호로 온 산문은 버리고 로그로만 알린다. 결과에
        담기지 않는 값이라 문서 전체를 접을 이유가 없다.

        구조화 출력 파싱이 실패하면 같은 프롬프트로 한 번 더 부른다. 본
        호출과 검증기 재시도 호출에 각각 한 번씩이다. 자세한 근거는
        _invoke_with_parse_retry에 적어 두었다.

        Raises:
            NarrationError: 프롬프트를 만들지 못했거나 호출이 터졌거나
                다시 물어도 계약이 깨졌거나, 다시 물어도 위반이 남았을 때
                던진다.
        """
        if request.summary is None and not request.blocks:
            return DocumentNarration(summary=None, narratives={})

        call_context = {
            "prompt_version": DOCUMENT_PROMPT_VERSION,
            "block_count": len(request.blocks),
            "with_summary": request.summary is not None,
        }
        parsed, elapsed = _invoke_with_parse_retry(
            structured=self._document_structured,
            template_path=DOCUMENT_TEMPLATE_PATH,
            render_kwargs={
                "purpose_sentence": request.purpose_sentence,
                "style_instruction": request.style_instruction,
                "summary": _block_payload(request.summary),
                "blocks": [_block_payload(block) for block in request.blocks],
            },
            event_prefix="document_narration",
            call_context=call_context,
            subject="문서 산문",
        )

        narratives, summary, violations = _split_response(
            parsed, want_summary=request.summary is not None
        )
        violations += document_narration_violations(
            request, narratives=narratives, summary=summary
        )
        narratives, violations = _drop_unknown_blocks(
            narratives,
            violations,
            allowed_ids={block.block_id for block in request.blocks},
            call_context=call_context,
        )

        retried = False
        if violations:
            logger.info(
                "document_narration_retry",
                violation_count=len(violations),
                reasons=[violation.reason for violation in violations],
                **call_context,
            )
            retried = True
            narratives, summary, violations, retry_elapsed = self._retry(
                request,
                narratives=narratives,
                summary=summary,
                violations=violations,
                call_context=call_context,
            )
            elapsed = round(elapsed + retry_elapsed, 3)

        if violations:
            logger.warning(
                "document_narration_failed",
                reason="contract_violation",
                violation_count=len(violations),
                reasons=[violation.reason for violation in violations],
                elapsed=elapsed,
                **call_context,
            )
            raise NarrationError(
                f"블록 산문이 계약을 어겼다: {violations[0].reason}"
            )

        logger.info(
            "document_narration_completed",
            elapsed=elapsed,
            narrative_count=len(narratives),
            retried=retried,
            **call_context,
        )
        return DocumentNarration(summary=summary, narratives=narratives)

    def _retry(
        self,
        request: DocumentNarrationRequest,
        *,
        narratives: dict[int, str],
        summary: SummaryNarrative | None,
        violations: tuple[NarrationViolation, ...],
        call_context: dict[str, Any],
    ) -> tuple[dict[int, str], SummaryNarrative | None, tuple[NarrationViolation, ...], float]:
        """위반한 자리만 사유와 함께 한 번 더 묻는다.

        통과한 블록은 다시 묻지 않고 읽기 전용 맥락으로만 실어 준다. 다시
        쓰게 하면 통과한 문장이 새로 깨질 수 있고, 문체를 맞출 근거는
        보여 주는 것으로 충분하다.

        Returns:
            합친 산문, 머리말, 남은 위반, 재시도 호출에 걸린 초를 돌려준다.
            남은 위반은 다시 물은 자리만 검사한 결과다.
        """
        requested_ids = {block.block_id for block in request.blocks}
        failed_ids = {
            violation.block_id
            for violation in violations
            if violation.block_id is not None
        }
        summary_failed = request.summary is not None and any(
            violation.block_id is None for violation in violations
        )
        retry_blocks = tuple(
            block for block in request.blocks if block.block_id in failed_ids
        )
        if not retry_blocks and not summary_failed:
            return narratives, summary, violations, 0.0

        reasons: dict[int | None, list[str]] = {}
        for violation in violations:
            reasons.setdefault(violation.block_id, []).append(violation.reason)

        retry_request = DocumentNarrationRequest(
            style_instruction=request.style_instruction,
            purpose_sentence=request.purpose_sentence,
            summary=request.summary if summary_failed else None,
            blocks=retry_blocks,
        )
        retry_context = {
            **call_context,
            "prompt_version": RETRY_PROMPT_VERSION,
            "block_count": len(retry_blocks),
        }
        parsed, elapsed = _invoke_with_parse_retry(
            structured=self._document_structured,
            template_path=RETRY_TEMPLATE_PATH,
            render_kwargs={
                "purpose_sentence": request.purpose_sentence,
                "style_instruction": request.style_instruction,
                "summary": _retry_summary_payload(
                    retry_request.summary, summary, reasons.get(None, [])
                ),
                "blocks": [
                    {
                        **_block_payload(block),
                        "previous": narratives.get(block.block_id, ""),
                        "reasons": reasons.get(block.block_id, []),
                    }
                    for block in retry_blocks
                ],
                "accepted": [
                    {"block_id": block_id, "narrative": narratives[block_id]}
                    for block_id in sorted(narratives)
                    if block_id in requested_ids and block_id not in failed_ids
                ],
            },
            event_prefix="document_narration_retry",
            call_context=retry_context,
            subject="문서 산문",
        )

        retry_narratives, retry_summary, remaining = _split_response(
            parsed, want_summary=summary_failed
        )
        retry_narratives, remaining = _drop_unknown_blocks(
            retry_narratives,
            remaining,
            allowed_ids=failed_ids,
            call_context=retry_context,
        )
        remaining += document_narration_violations(
            retry_request, narratives=retry_narratives, summary=retry_summary
        )

        merged = {
            block_id: text
            for block_id, text in narratives.items()
            if block_id in requested_ids and block_id not in failed_ids
        }
        merged.update(
            {
                block_id: text
                for block_id, text in retry_narratives.items()
                if block_id in failed_ids
            }
        )
        return (
            merged,
            retry_summary if summary_failed else summary,
            remaining,
            elapsed,
        )

    def explain_change(self, request: ChangeExplanationRequest) -> str:
        """바뀐 블록의 수정 이유를 한 문장으로 받는다.

        로그 규칙은 산문과 같다. 판본과 개수만 남기고 이전·이후 문장,
        새 인용, 받아 온 이유는 남기지 않는다. 실패도 예외 종류만 남기고
        예외 메시지와 역추적은 남기지 않는다. 파싱 예외 메시지에는 모델이
        돌려준 문장이 통째로 실려 있고, 역추적에는 프롬프트가 실릴 수 있기
        때문이다.

        Raises:
            NarrationError: 프롬프트를 만들지 못했거나 호출이 터졌거나
                계약을 어겼거나 빈 문장을 받았을 때 던진다.
        """
        call_context = {
            "prompt_version": EXPLAIN_PROMPT_VERSION,
            "before_count": len(request.before_statements),
            "after_count": len(request.after_statements),
            "new_source_count": len(request.new_sources),
        }
        parsed, elapsed = _invoke_contract(
            structured=self._reason_structured,
            template_path=EXPLAIN_TEMPLATE_PATH,
            render_kwargs={
                "heading": request.heading,
                "before_statements": list(request.before_statements),
                "after_statements": list(request.after_statements),
                "new_sources": list(request.new_sources),
                "purpose_sentence": request.purpose_sentence,
            },
            event_prefix="block_change_explanation",
            call_context=call_context,
            subject="블록 변경 이유",
        )

        value = str(parsed.reason).strip()
        if not value:
            logger.warning(
                "block_change_explanation_failed",
                reason="empty_reason",
                elapsed=elapsed,
                **call_context,
            )
            raise NarrationError("블록 변경 이유가 비었다.")

        logger.info(
            "block_change_explanation_completed",
            elapsed=elapsed,
            reason_length=len(value),
            **call_context,
        )
        return value


def _block_payload(block: BlockNarrationInput | None) -> dict[str, Any] | None:
    """블록 재료를 템플릿이 읽을 모양으로 옮긴다.

    튜플을 목록으로 편다. 템플릿에서 길이를 재고 되도는 데 목록이 읽기
    쉽고, 자료형이 프롬프트 쪽으로 새지 않는다.
    """
    if block is None:
        return None
    return {
        "block_id": block.block_id,
        "block_kind": block.block_kind,
        "heading": block.heading,
        "topic_hint": block.topic_hint,
        "statements": list(block.statements),
        "edges": list(block.edges),
        "hints": list(block.hints),
        "variants": [(body, list(quotes)) for body, quotes in block.variants],
    }


def _retry_summary_payload(
    request_summary: BlockNarrationInput | None,
    summary: SummaryNarrative | None,
    reasons: list[str],
) -> dict[str, Any] | None:
    """다시 물을 머리말의 재료와 지적을 템플릿 모양으로 옮긴다."""
    payload = _block_payload(request_summary)
    if payload is None:
        return None
    payload["previous"] = (
        [(field, getattr(summary, field)) for field in _SUMMARY_FIELDS]
        if summary is not None
        else None
    )
    payload["reasons"] = reasons
    return payload


def _split_response(
    parsed: _DocumentNarrationContract,
    *,
    want_summary: bool,
) -> tuple[dict[int, str], SummaryNarrative | None, tuple[NarrationViolation, ...]]:
    """응답 목록을 블록 번호별 산문과 머리말로 가른다.

    같은 번호가 두 번 오면 먼저 온 값도 쓰지 않는다. 둘 중 어느 쪽이
    그 블록의 답인지 정할 근거가 없어, 고르는 대신 다시 묻는다.

    산문과 머리말 세 칸은 앞뒤 공백을 잘라서 담는다. 모델이 붙여 보내는
    줄바꿈과 들여쓰기가 그대로 문서에 실리면 안 되기 때문이다.

    머리말은 묻지 않았으면 버린다. 세 칸이 모두 비어 오면 머리말이 오지
    않은 것으로 본다. 칸마다 빈 값이라고 지적하는 것보다 머리말이 없다고
    한 번 지적하는 편이 고칠 거리가 분명하다.

    Returns:
        블록 번호별 산문, 머리말, 가르는 동안 찾은 위반을 돌려준다.
    """
    narratives: dict[int, str] = {}
    violations: list[NarrationViolation] = []
    seen: set[int] = set()
    for item in parsed.narratives:
        if item.block_id in seen:
            narratives.pop(item.block_id, None)
            violations.append(
                NarrationViolation(
                    block_id=item.block_id,
                    reason="같은 블록에 산문이 두 번 왔다. 블록마다 한 번만 답하라",
                )
            )
            continue
        seen.add(item.block_id)
        narratives[item.block_id] = str(item.narrative).strip()

    summary: SummaryNarrative | None = None
    if want_summary:
        values = {
            field: str(getattr(parsed, field) or "").strip()
            for field in _SUMMARY_FIELDS
        }
        if any(values.values()):
            summary = SummaryNarrative(**values)

    return narratives, summary, tuple(violations)


def _drop_unknown_blocks(
    narratives: dict[int, str],
    violations: tuple[NarrationViolation, ...],
    *,
    allowed_ids: set[int],
    call_context: dict[str, Any],
) -> tuple[dict[int, str], tuple[NarrationViolation, ...]]:
    """묻지 않은 블록 번호로 온 산문과 그 위반을 버린다.

    없는 번호를 지어내는 것은 구조화 출력에서 흔한 실패다. 그 산문은
    어차피 결과에 담기지 않으므로, 위반으로 세어 문서 전체를 접을 이유가
    없다. 묻지 않은 것이 딸려 온 사실은 로그로만 남긴다.

    다시 물을 때도 같은 규칙을 쓴다. 이미 통과한 블록의 산문이 재시도
    응답에 섞여 와도 버리고 다시 검사하지 않는다. 통과한 문장은 1차 응답의
    것을 그대로 쓴다.

    Args:
        narratives: 블록 번호별 산문을 받는다.
        violations: 지금까지 찾은 위반을 받는다.
        allowed_ids: 이번에 답을 받기로 한 블록 번호를 받는다.
        call_context: 로그에 함께 남길 항목을 받는다.

    Returns:
        허용된 번호만 남긴 산문과 위반을 돌려준다.
    """
    unknown_ids = {
        block_id for block_id in narratives if block_id not in allowed_ids
    }
    unknown_ids |= {
        violation.block_id
        for violation in violations
        if violation.block_id is not None and violation.block_id not in allowed_ids
    }
    if not unknown_ids:
        return narratives, violations

    logger.warning(
        "document_narration_unknown_blocks",
        unknown_block_ids=sorted(unknown_ids),
        **call_context,
    )
    kept_narratives = {
        block_id: text
        for block_id, text in narratives.items()
        if block_id in allowed_ids
    }
    kept_violations = tuple(
        violation
        for violation in violations
        if violation.block_id is None or violation.block_id in allowed_ids
    )
    return kept_narratives, kept_violations


def _invoke_contract(
    *,
    structured: Any,
    template_path: str,
    render_kwargs: dict[str, Any],
    event_prefix: str,
    call_context: dict[str, Any],
    subject: str,
) -> tuple[Any, float]:
    """프롬프트를 렌더해 구조화 출력을 부르고 계약 객체를 돌려준다.

    묻는 것이 문서 산문이든 변경 이유든 여기까지는 같다. 렌더·호출·계약
    확인 세 단계이고, 어느 단계에서 넘어져도 NarrationError 하나로 감싼다.
    받아 온 값을 들여다보는 일은 계약마다 달라 부르는 쪽에 남긴다.

    Args:
        structured: 구조화 출력이 묶인 모델을 받는다.
        template_path: 부를 프롬프트 템플릿 경로를 받는다.
        render_kwargs: 템플릿에 넘길 변수를 받는다.
        event_prefix: 로그 이벤트 이름 앞머리를 받는다. 뒤에
            started·failed가 붙는다.
        call_context: 모든 로그에 함께 남길 항목을 받는다. 원문과 받아 온
            문장은 여기에 담지 않는다.
        subject: 예외 문구에 쓸 대상 이름을 받는다.

    Returns:
        계약 객체와 호출에 걸린 초를 함께 돌려준다. 걸린 초는 부르는 쪽이
        완료·실패 로그에 그대로 싣는다.

    Raises:
        NarrationError: 프롬프트를 만들지 못했거나 호출이 터졌을 때 던진다.
        _ContractParseError: 호출은 됐는데 받아 온 값을 계약 객체로 옮기지
            못했을 때 던진다. NarrationError의 하위 예외라, 이 부류를
            가리지 않는 호출부에는 위와 같아 보인다.
    """
    logger.info(f"{event_prefix}_started", **call_context)

    try:
        rendered = prompt_loader.get_prompt(template_path, **render_kwargs)
    except Exception as error:
        logger.warning(
            f"{event_prefix}_failed",
            reason="prompt_render_error",
            error_type=type(error).__name__,
            **call_context,
        )
        raise NarrationError(f"{subject} 프롬프트를 만들지 못했다.") from error

    started = time.perf_counter()
    try:
        response = retry_llm_call(
            lambda: structured.invoke(rendered), subject=event_prefix
        )
    except Exception as error:
        logger.warning(
            f"{event_prefix}_failed",
            reason="llm_call_error",
            error_type=type(error).__name__,
            elapsed=round(time.perf_counter() - started, 3),
            **call_context,
        )
        raise NarrationError(f"{subject} 호출이 실패했다.") from error
    elapsed = round(time.perf_counter() - started, 3)

    parsed = response.get("parsed")
    if parsed is None:
        error = response.get("parsing_error")
        logger.warning(
            f"{event_prefix}_failed",
            reason="contract_violation",
            error_type=type(error).__name__ if error is not None else "unknown",
            elapsed=elapsed,
            **call_context,
        )
        raise _ContractParseError(f"{subject} 계약이 깨졌다.")

    return parsed, elapsed


def _invoke_with_parse_retry(
    *,
    structured: Any,
    template_path: str,
    render_kwargs: dict[str, Any],
    event_prefix: str,
    call_context: dict[str, Any],
    subject: str,
) -> tuple[Any, float]:
    """계약 파싱이 실패하면 같은 프롬프트로 한 번만 더 부른다.

    파싱 실패는 비결정적이다. 실측에서 모델이 narratives를 목록이 아니라
    JSON 문자열로 돌려주는 일이 있었고, 같은 프롬프트를 다시 물으면 제
    모양으로 온다. 피드백을 붙이지 않고 그대로 다시 묻는 이유가 여기에
    있다. 고칠 거리를 알려 줄 것이 없고, 프롬프트를 바꾸면 첫 호출과 다른
    조건이 되어 무엇이 통한 것인지 알 수 없다.

    다시 부르는 것은 파싱 실패뿐이다. 프롬프트 렌더 실패와 호출 실패는
    같은 조건에서 같은 결과가 나올 쪽이 크다. 인증이나 요청 길이처럼 다시
    불러도 똑같이 터지는 사유가 섞여 있어, 실패를 두 배로 늦출 뿐이다.

    예산은 이 함수 한 번에 한 번이다. 본 호출과 검증기 재시도 호출이 각각
    이 함수를 지나므로, 한 문서를 서술하는 동안 모델을 부르는 횟수는 최대
    네 번이다.

    Returns:
        _invoke_contract가 돌려주는 계약 객체와 마지막 호출에 걸린 초를
        그대로 돌려준다.

    Raises:
        NarrationError: 다시 물어도 파싱이 실패했거나, 다시 부르지 않는
            부류의 실패가 났을 때 던진다.
    """
    try:
        return _invoke_contract(
            structured=structured,
            template_path=template_path,
            render_kwargs=render_kwargs,
            event_prefix=event_prefix,
            call_context=call_context,
            subject=subject,
        )
    except _ContractParseError:
        logger.info(
            "document_narration_parse_retry",
            reason="contract_violation",
            **call_context,
        )

    return _invoke_contract(
        structured=structured,
        template_path=template_path,
        render_kwargs=render_kwargs,
        event_prefix=event_prefix,
        call_context=call_context,
        subject=subject,
    )
