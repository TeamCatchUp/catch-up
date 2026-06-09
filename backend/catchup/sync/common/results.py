from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(slots=True, frozen=True)
class EventSyncResult:
    synced_count: int = 0
    error_count: int = 0
    skipped: bool = False


@dataclass(slots=True, frozen=True)
class TargetSyncResult(EventSyncResult):
    """Compatibility name for the existing worker target result."""


@dataclass(slots=True, frozen=True)
class PageSyncResult:
    synced_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    deleted_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)
