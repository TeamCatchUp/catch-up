"""Typed vector-store v2 ingestion records."""

from catchup.sync.ingestion.vector_records.github_pr import GithubPrData
from catchup.sync.ingestion.vector_records.github_pr import GithubPrDataPart
from catchup.sync.ingestion.vector_records.github_pr import GithubPrMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrUserMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrVectorRecord
from catchup.sync.ingestion.vector_records.github_pr_mapper import (
    GithubPrV2RecordMapper,
)

__all__ = [
    "GithubPrData",
    "GithubPrDataPart",
    "GithubPrMetadata",
    "GithubPrUserMetadata",
    "GithubPrV2RecordMapper",
    "GithubPrVectorRecord",
]
