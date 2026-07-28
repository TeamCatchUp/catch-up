from __future__ import annotations

from typing import Protocol

from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)


class KnowledgeExtractionPort(Protocol):
    """원문 하나에서 지식 후보를 뽑는 경계를 정의한다."""

    async def extract(
        self,
        request: KnowledgeExtractionRequest,
    ) -> KnowledgeCandidateBatch: ...
