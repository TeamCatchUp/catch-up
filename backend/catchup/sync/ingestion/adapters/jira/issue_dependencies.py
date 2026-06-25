from __future__ import annotations

from dataclasses import dataclass

from catchup.components.summarizer import SummarizerService
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.jira.client import JiraApiClient
from catchup.connectors.jira.field_mapper import JiraFieldMapper
from catchup.sync.ingestion.adapters.jira.issue_v2_document_builder import (
    JiraIssueV2DocumentBuilder,
)
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
    vector_store: VectorStore | None = None
    v2_document_builder: JiraIssueV2DocumentBuilder | None = None
