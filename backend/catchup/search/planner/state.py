from typing import TypedDict

from catchup.rag.schemas.structures import ManualSearchQuery

_QUERY_CACHE_MAX_SIZE = 20


class ManualSearchState(TypedDict):
    original_query: str
    query_cache: dict[str, ManualSearchQuery]
    query_cache_hit: bool | None
