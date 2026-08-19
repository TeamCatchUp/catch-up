"""LLM에게 블록 산문을 물어보는 어댑터를 정의한다."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.language_models import BaseChatModel

from catchup.knowledge_maintenance.adapters.llm.prompt_versioning import (
    versioned_prompt,
)
from catchup.knowledge_maintenance.contracts.block_narration import ChangeReasonContract
from catchup.knowledge_maintenance.contracts.block_narration import NarrativeContract
from catchup.knowledge_maintenance.ports.narrator import ChangeExplanationRequest
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.knowledge_maintenance.ports.narrator import NarrationRequest
from catchup.observability.logging import get_logger
from catchup.prompts.loader import prompt_loader

TEMPLATE_PATH = "knowledge_maintenance/narrate_block.j2"
PROMPT_VERSION = versioned_prompt(TEMPLATE_PATH)
EXPLAIN_TEMPLATE_PATH = "knowledge_maintenance/explain_block_change.j2"
EXPLAIN_PROMPT_VERSION = versioned_prompt(EXPLAIN_TEMPLATE_PATH)

logger = get_logger(__name__)


class LlmBlockNarrator:
    """블록 재료를 주고 산문 한 문단을 구조화 출력으로 받는다.

    실패는 예외다. 어휘 수렴 어댑터가 None을 돌려주는 것과 다른 이유는,
    저쪽은 이번 라운드를 무발행으로 끝내면 되지만 이쪽은 산문이 반쪽인
    문서를 검수자에게 올리지 않는 것이 결정이기 때문이다.

    재시도를 두지 않는다. 실패한 노드는 이번 실행에서 접히고 다음 실행이
    같은 자리를 다시 컴파일하므로, 한 호출 안에서 조를 이유가 없다.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._structured = llm.with_structured_output(
            NarrativeContract,
            method="function_calling",
            include_raw=True,
        )
        self._reason_structured = llm.with_structured_output(
            ChangeReasonContract,
            method="function_calling",
            include_raw=True,
        )

    def narrate(self, request: NarrationRequest) -> str:
        """블록 하나를 산문 한 문단으로 옮긴다.

        무엇을 근거로 무엇을 물었는지만 로그에 남긴다. 인용 원문과 산문은
        싣지 않는다 — 원문은 상담·대화 조각이고 감사 로그는 오래 남기
        때문이다. 실패도 마찬가지라 예외 종류만 남기고 예외 메시지와
        역추적은 남기지 않는다. 파싱 예외 메시지에는 모델이 돌려준 산문이
        통째로 실려 있고, 역추적에는 프롬프트가 실릴 수 있기 때문이다.

        Raises:
            NarrationError: 프롬프트를 만들지 못했거나 호출이 터졌거나
                계약을 어겼거나 빈 문장을 받았을 때 던진다.
        """
        return _run_structured_call(
            structured=self._structured,
            template_path=TEMPLATE_PATH,
            render_kwargs={
                "block_kind": request.block_kind,
                "heading": request.heading,
                "topic_hint": request.topic_hint,
                "statements": list(request.statements),
                "edges": list(request.edges),
                "hints": list(request.hints),
                "variants": [
                    (body, list(items)) for body, items in request.variants
                ],
                "style_instruction": request.style_instruction,
                "purpose_sentence": request.purpose_sentence,
            },
            event_prefix="block_narration",
            call_context={
                "prompt_version": PROMPT_VERSION,
                "block_kind": request.block_kind,
                "statement_count": len(request.statements),
                "variant_count": len(request.variants),
            },
            field="narrative",
            subject="블록 산문",
            empty_message="블록 산문이 비었다.",
        )

    def explain_change(self, request: ChangeExplanationRequest) -> str:
        """바뀐 블록의 수정 이유를 한 문장으로 받는다.

        로그 규칙은 산문과 같다. 판본과 개수만 남기고 이전·이후 문장,
        새 인용, 받아 온 이유는 남기지 않는다. 실패도 예외 종류만 남기고
        예외 메시지와 역추적은 남기지 않는다.

        Raises:
            NarrationError: 프롬프트를 만들지 못했거나 호출이 터졌거나
                계약을 어겼거나 빈 문장을 받았을 때 던진다.
        """
        return _run_structured_call(
            structured=self._reason_structured,
            template_path=EXPLAIN_TEMPLATE_PATH,
            render_kwargs={
                "heading": request.heading,
                "before_statements": list(request.before_statements),
                "after_statements": list(request.after_statements),
                "new_sources": list(request.new_sources),
                "style_instruction": request.style_instruction,
                "purpose_sentence": request.purpose_sentence,
            },
            event_prefix="block_change_explanation",
            call_context={
                "prompt_version": EXPLAIN_PROMPT_VERSION,
                "before_count": len(request.before_statements),
                "after_count": len(request.after_statements),
                "new_source_count": len(request.new_sources),
            },
            field="reason",
            subject="블록 변경 이유",
            empty_message="블록 변경 이유가 비었다.",
        )


def _run_structured_call(
    *,
    structured: Any,
    template_path: str,
    render_kwargs: dict[str, Any],
    event_prefix: str,
    call_context: dict[str, Any],
    field: str,
    subject: str,
    empty_message: str,
) -> str:
    """프롬프트를 렌더해 구조화 출력을 부르고 칸 하나를 꺼낸다.

    산문과 변경 이유는 묻는 것만 다를 뿐 밟는 단계가 같다. 렌더·호출·계약
    확인·빈 값 확인 네 단계이고, 어느 단계에서 넘어져도 NarrationError
    하나로 감싼다. 두 벌로 적어 두면 로그 규칙이 한쪽에서만 바뀔 수 있어
    한자리에 모은다.

    Args:
        structured: 구조화 출력이 묶인 모델을 받는다.
        template_path: 부를 프롬프트 템플릿 경로를 받는다.
        render_kwargs: 템플릿에 넘길 변수를 받는다.
        event_prefix: 로그 이벤트 이름 앞머리를 받는다. 뒤에
            started·completed·failed가 붙는다.
        call_context: 모든 로그에 함께 남길 항목을 받는다. 원문과 받아 온
            문장은 여기에 담지 않는다.
        field: 계약에서 꺼낼 칸 이름을 받는다. 실패 이유와 길이 항목의
            이름도 이 값에서 만든다.
        subject: 예외 문구에 쓸 대상 이름을 받는다.
        empty_message: 빈 값일 때 쓸 예외 문구를 받는다.

    Returns:
        앞뒤 공백을 덜어 낸 칸 값을 돌려준다.

    Raises:
        NarrationError: 프롬프트를 만들지 못했거나 호출이 터졌거나 계약을
            어겼거나 빈 문장을 받았을 때 던진다.
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
        response = structured.invoke(rendered)
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
        raise NarrationError(f"{subject} 계약이 깨졌다.")

    value = str(getattr(parsed, field)).strip()
    if not value:
        logger.warning(
            f"{event_prefix}_failed",
            reason=f"empty_{field}",
            elapsed=elapsed,
            **call_context,
        )
        raise NarrationError(empty_message)

    logger.info(
        f"{event_prefix}_completed",
        elapsed=elapsed,
        **{f"{field}_length": len(value)},
        **call_context,
    )
    return value
