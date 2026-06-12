"""Typed vector-store v2 ingestion records."""

from catchup.sync.ingestion.vector_records.github_issue import GithubIssueData
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueDataPart
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueMetadata
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueUserMetadata
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueVectorRecord
from catchup.sync.ingestion.vector_records.github_issue_mapper import (
    GithubIssueV2RecordMapper,
)
from catchup.sync.ingestion.vector_records.github_pr import GithubPrData
from catchup.sync.ingestion.vector_records.github_pr import GithubPrDataPart
from catchup.sync.ingestion.vector_records.github_pr import GithubPrMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrUserMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrVectorRecord
from catchup.sync.ingestion.vector_records.github_pr_mapper import (
    GithubPrV2RecordMapper,
)

__all__ = [
    "GithubIssueData",
    "GithubIssueDataPart",
    "GithubIssueMetadata",
    "GithubIssueUserMetadata",
    "GithubIssueV2RecordMapper",
    "GithubIssueVectorRecord",
    "GithubPrData",
    "GithubPrDataPart",
    "GithubPrMetadata",
    "GithubPrUserMetadata",
    "GithubPrV2RecordMapper",
    "GithubPrVectorRecord",
]
