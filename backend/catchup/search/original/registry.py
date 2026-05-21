from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from catchup.db.models import SourceType
from catchup.search.original.base import OriginalContentResolver


class OriginalResolverNotFoundError(LookupError):
    """Raised when no original-content resolver is registered for a route."""


@dataclass
class OriginalResolverRegistry:
    _resolvers: dict[tuple[SourceType, str], OriginalContentResolver] = field(
        default_factory=dict
    )

    def register(
        self,
        *,
        connector: SourceType,
        entity_type: str,
        resolver: OriginalContentResolver,
    ) -> None:
        self._resolvers[(connector, entity_type)] = resolver

    def get(
        self,
        *,
        connector: SourceType,
        entity_type: str,
    ) -> OriginalContentResolver:
        resolver = self._resolvers.get((connector, entity_type))
        if resolver is None:
            raise OriginalResolverNotFoundError(
                f"unsupported original document route: {connector.value}:{entity_type}"
            )
        return resolver
