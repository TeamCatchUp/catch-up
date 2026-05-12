from typing import TypedDict

from catchup.rag.schemas.structures import VectorDbSearchQuery


class ManualSearchState(TypedDict):
    original_query: str
    last_planned_query: str
    planned_search: VectorDbSearchQuery | None
