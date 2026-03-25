"""Jira collaborator가 공유하는 runtime 의존성 묶음."""

from dataclasses import dataclass

from catchup.components.summarizer import SummarizerService
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.connectors.jira.client import JiraApiClient
from catchup.connectors.jira.transformers import JiraTransformer


@dataclass(slots=True, frozen=True)
class JiraRuntime:
    cloud_id: str
    site_url: str
    client: JiraApiClient
    transformer: JiraTransformer
    repository: PGVectorRepository
    summarizer: SummarizerService | None = None
