from __future__ import annotations

import asyncio
import time

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from pydantic import ConfigDict

from catchup.knowledge_maintenance.domain.entity_resolution import IdentityVerdict
from catchup.knowledge_maintenance.ports.identity_judge import JudgeCandidate
from catchup.observability.logging import get_logger
from catchup.prompts.loader import prompt_loader

TEMPLATE_PATH = "knowledge_maintenance/judge_entity_identity.j2"

logger = get_logger(__name__)


class IdentityJudgeOutput(BaseModel):
    """판정 LLM의 구조화 출력 계약을 정의한다.

    Attributes:
        same: 그룹이 같은 대상인지 나타낸다.
        reason: 판정의 근거 한 문장을 담는다.
        canonical_type: same일 때 제안하는 entity 종류를 나타낸다.
        canonical_name: same일 때 제안하는 표시 이름을 나타낸다.
    """

    model_config = ConfigDict(frozen=True)

    same: bool
    reason: str
    canonical_type: str | None = None
    canonical_name: str | None = None


class BedrockIdentityJudge:
    """같은 이름 그룹의 identity를 LLM으로 판정한다.

    port는 sync다. 서비스와 러너가 이벤트 루프를 몰라도 되도록 비동기
    호출을 여기서 감싼다.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._structured = llm.with_structured_output(
            IdentityJudgeOutput,
            method="function_calling",
            include_raw=True,
        )

    def judge(
        self,
        group: tuple[JudgeCandidate, ...],
    ) -> IdentityVerdict:
        """그룹이 같은 대상인지 판정한다. 계약 위반이면 예외를 올린다."""
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            candidates=group,
        )

        started = time.perf_counter()
        response = asyncio.run(self._structured.ainvoke(rendered))
        elapsed = round(time.perf_counter() - started, 3)

        parsed = response.get("parsed")
        if parsed is None:
            error = response.get("parsing_error")
            logger.warning(
                "identity_judge_rejected",
                reason="contract_violation",
                detail=str(error) if error is not None else "unknown",
                group_size=len(group),
                elapsed=elapsed,
            )
            raise ValueError(
                f"판정 출력이 계약을 만족하지 않는다: {error}"
            )

        logger.info(
            "identity_judge_completed",
            same=parsed.same,
            group_size=len(group),
            elapsed=elapsed,
        )
        return IdentityVerdict(
            same=parsed.same,
            reason=parsed.reason,
            proposed_type=parsed.canonical_type,
            proposed_name=parsed.canonical_name,
        )
