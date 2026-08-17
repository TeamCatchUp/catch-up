"""LLM에게 블록 산문을 물어보는 어댑터를 정의한다."""

from __future__ import annotations

import time

from langchain_core.language_models import BaseChatModel

from catchup.knowledge_maintenance.adapters.llm.prompt_versioning import (
    versioned_prompt,
)
from catchup.knowledge_maintenance.contracts.block_narration import NarrativeContract
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.knowledge_maintenance.ports.narrator import NarrationRequest
from catchup.observability.logging import get_logger
from catchup.prompts.loader import prompt_loader

TEMPLATE_PATH = "knowledge_maintenance/narrate_block.j2"
PROMPT_VERSION = versioned_prompt(TEMPLATE_PATH)

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
        call_context = {
            "prompt_version": PROMPT_VERSION,
            "block_kind": request.block_kind,
            "statement_count": len(request.statements),
            "variant_count": len(request.variants),
        }
        logger.info("block_narration_started", **call_context)

        try:
            rendered = prompt_loader.get_prompt(
                TEMPLATE_PATH,
                block_kind=request.block_kind,
                heading=request.heading,
                topic_hint=request.topic_hint,
                statements=list(request.statements),
                edges=list(request.edges),
                hints=list(request.hints),
                variants=[
                    (body, list(items)) for body, items in request.variants
                ],
                style_instruction=request.style_instruction,
                purpose_sentence=request.purpose_sentence,
            )
        except Exception as error:
            logger.warning(
                "block_narration_failed",
                reason="prompt_render_error",
                error_type=type(error).__name__,
                **call_context,
            )
            raise NarrationError("블록 산문 프롬프트를 만들지 못했다.") from error

        started = time.perf_counter()
        try:
            response = self._structured.invoke(rendered)
        except Exception as error:
            logger.warning(
                "block_narration_failed",
                reason="llm_call_error",
                error_type=type(error).__name__,
                elapsed=round(time.perf_counter() - started, 3),
                **call_context,
            )
            raise NarrationError("블록 산문 호출이 실패했다.") from error
        elapsed = round(time.perf_counter() - started, 3)

        parsed = response.get("parsed")
        if parsed is None:
            error = response.get("parsing_error")
            logger.warning(
                "block_narration_failed",
                reason="contract_violation",
                error_type=type(error).__name__ if error is not None else "unknown",
                elapsed=elapsed,
                **call_context,
            )
            raise NarrationError("블록 산문 계약이 깨졌다.")

        narrative = parsed.narrative.strip()
        if not narrative:
            logger.warning(
                "block_narration_failed",
                reason="empty_narrative",
                elapsed=elapsed,
                **call_context,
            )
            raise NarrationError("블록 산문이 비었다.")

        logger.info(
            "block_narration_completed",
            elapsed=elapsed,
            narrative_length=len(narrative),
            **call_context,
        )
        return narrative
