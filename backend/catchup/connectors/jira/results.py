from dataclasses import dataclass
from dataclasses import field


@dataclass(slots=True, frozen=True)
class JiraRecordGapItem:
    record_type: str
    expected_count: int = 0
    stored_count: int = 0
    missing_count: int = 0
    missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class JiraRecordGapReport:
    records: list[JiraRecordGapItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class JiraRecordRetryItem:
    record_type: str
    requested_ids: list[str] = field(default_factory=list)
    retried_count: int = 0
    succeeded_count: int = 0
    failed_ids: list[str] = field(default_factory=list)
    remaining_missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class JiraRecordRetryResult:
    records: list[JiraRecordRetryItem] = field(default_factory=list)
