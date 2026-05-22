from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from typing import TypedDict

from catchup.rag.schemas.structures import ManualSearchQuery

_QUERY_CACHE_MAX_SIZE = 20


@dataclass
class CachedSearch:
    planned: ManualSearchQuery
    searched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ManualSearchState(TypedDict):
    original_query: str
    query_cache: dict[str, CachedSearch]
    query_cache_hit: bool | None
