from typing import Any
from langchain_core.documents import Document

class BaseVectorDbService:
    async def hybrid_search(
        self,
        query: str,
        k: int = 4,
        weights: list[float] = [0.3, 0.5, 0.2],
        tool_filters: list[Any] | None = None,
        temporal_filters: list[Any] | None = None,
        keyword_tokens: list[str] | None = None,
        offset: int = 0,
        score_threshold: float = 0.4,
    ) -> list[Document]:
        raise NotImplementedError

    async def hybrid_search_batch(
        self,
        queries: list[dict[str, Any]],
        k: int = 10,
        weights: list[float] = [0.6, 0.25, 0.15],
        tool_filters: list[Any] | None = None,
    ) -> list[list[Document]]:
        raise NotImplementedError
