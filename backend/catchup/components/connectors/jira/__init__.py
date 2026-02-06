"""
Jira Connector Module

Jira Cloud API 연동 및 PGVector 동기화 기능 제공.

Components:
    - JiraApiClient: Jira REST API 클라이언트
    - JiraFieldMapper: 커스텀 필드 ID → 이름 매퍼
    - JiraTransformer: Jira 엔티티 → LangChain Document 변환기
    - JiraIngestionService: 동기화 서비스
"""

from catchup.components.connectors.jira.client import (
    JiraApiClient,
    JiraApiError,
    JiraAuthError,
    JiraRateLimitError,
)
from catchup.components.connectors.jira.field_mapper import JiraFieldMapper
from catchup.components.connectors.jira.service import JiraIngestionService
from catchup.components.connectors.jira.transformers import JiraTransformer

__all__ = [
    "JiraApiClient",
    "JiraApiError",
    "JiraAuthError",
    "JiraRateLimitError",
    "JiraFieldMapper",
    "JiraTransformer",
    "JiraIngestionService",
]
