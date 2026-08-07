"""LLM에게 어휘 수렴안을 물어보는 어댑터를 정의한다."""

from __future__ import annotations

import time
from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel

from catchup.knowledge_maintenance.adapters.llm.prompt_versioning import (
    versioned_prompt,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    PredicateUsage,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import RelationUsage
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    VocabularyConvergenceProposal,
)
from catchup.observability.logging import get_logger
from catchup.prompts.loader import prompt_loader

TEMPLATE_PATH = "knowledge_maintenance/converge_vocabulary.j2"
PROMPT_VERSION = versioned_prompt(TEMPLATE_PATH)

logger = get_logger(__name__)


class LlmVocabularyConverger:
    """OOV 사용 현황을 보여 주고 수렴안을 구조화 출력으로 받는다.

    실패는 예외가 아니라 `None`이다. 수렴은 배치 작업이고 한 번 못 물어봤다고
    러너 전체를 깨뜨릴 이유가 없다. 호출자는 `None`을 무발행 종료로 읽는다.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._structured = llm.with_structured_output(
            VocabularyConvergenceProposal,
            method="function_calling",
            include_raw=True,
        )

    async def propose(
        self,
        *,
        current: ExtractionVocabulary,
        predicate_usage: Sequence[PredicateUsage],
        relation_usage: Sequence[RelationUsage],
    ) -> VocabularyConvergenceProposal | None:
        """현행 사전과 OOV 현황을 주고 수렴안을 받는다."""
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            current=current,
            predicate_usage=list(predicate_usage),
            relation_usage=list(relation_usage),
        )

        # 무엇을 근거로 무엇을 물었는지 남긴다. 이름과 예문은 싣지 않는다.
        # 예문은 상담 원문 조각이고 감사 로그는 오래 남기 때문이다.
        call_context = {
            "prompt_version": PROMPT_VERSION,
            "ontology_version": current.snapshot_id or None,
            "oov_predicate_count": len(predicate_usage),
            "oov_relation_count": len(relation_usage),
        }
        logger.info("vocabulary_convergence_started", **call_context)

        started = time.perf_counter()
        try:
            response = await self._structured.ainvoke(rendered)
        except Exception as error:
            logger.exception(
                "vocabulary_convergence_failed",
                reason="llm_call_error",
                error_type=type(error).__name__,
                elapsed=round(time.perf_counter() - started, 3),
                **call_context,
            )
            return None
        elapsed = round(time.perf_counter() - started, 3)

        parsed = response.get("parsed")
        if parsed is None:
            error = response.get("parsing_error")
            logger.warning(
                "vocabulary_convergence_failed",
                reason="contract_violation",
                detail=str(error) if error is not None else "unknown",
                elapsed=elapsed,
                **call_context,
            )
            return None

        logger.info(
            "vocabulary_convergence_completed",
            elapsed=elapsed,
            absorption_count=len(parsed.absorptions),
            proposed_predicate_count=len(parsed.predicate_entries),
            proposed_relation_count=len(parsed.relation_entries),
            **call_context,
        )
        return parsed
