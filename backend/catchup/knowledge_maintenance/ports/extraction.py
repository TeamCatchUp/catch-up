from __future__ import annotations

from typing import Protocol

from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)


class ExtractionContractError(ValueError):
    """LLM 응답이 추출 계약을 만족하지 않음을 나타낸다."""

    def __init__(self, message: str, *, raw_output: dict | None = None) -> None:
        super().__init__(message)
        self.raw_output = raw_output


class ExtractionAPIError(RuntimeError):
    """LLM 호출 자체가 실패했음을 나타낸다."""


class KnowledgeExtractionPort(Protocol):
    """원문 하나에서 지식 후보를 뽑는 경계를 정의한다."""

    async def extract(
        self,
        request: KnowledgeExtractionRequest,
    ) -> KnowledgeCandidateBatch: ...
