from __future__ import annotations

from dataclasses import dataclass

from catchup.components.summarizer import SummarizerService
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.connectors.jira.client import JiraApiClient
from catchup.connectors.jira.field_mapper import JiraFieldMapper
from catchup.sync.ingestion.document_builders.jira import JiraTransformer


@dataclass(slots=True)
class JiraIssueIngestionDependencies:
    cloud_id: str
    site_url: str
    client: JiraApiClient
    field_mapper: JiraFieldMapper
    transformer: JiraTransformer
    repository: PGVectorRepository
    summarizer: SummarizerService | None
