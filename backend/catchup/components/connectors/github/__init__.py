"""
GitHub Connector

GitHub 데이터 수집 및 PGVector 적재를 위한 커넥터.

주요 컴포넌트:
- GitHubApiClient: GitHub REST API 클라이언트
- GitHubTransformer: API 응답 → LangChain Document 변환
- GitHubIngestionService: 데이터 동기화 서비스
"""

from catchup.components.connectors.github.client import (
    GitHubApiClient,
    GitHubApiError,
    GitHubRateLimitError,
    GitHubAuthError,
    GitHubNotFoundError,
)
from catchup.components.connectors.github.schemas import (
    GitHubUser,
    GitHubLabel,
    GitHubMilestone,
    GitHubReaction,
    GitHubIssue,
    GitHubIssueComment,
    GitHubPullRequest,
    GitHubPRReview,
    GitHubCommit,
    GitHubCommitFile,
    GitHubRepository,
    PRFileContext,
    PRComment,
)
from catchup.components.connectors.github.transformers import GitHubTransformer
from catchup.components.connectors.github.service import (
    GitHubIngestionService,
    GithubService,
)
from catchup.components.connectors.github.factory import (
    get_github_service,
    create_github_ingestion_service,
)

__all__ = [
    # Client
    "GitHubApiClient",
    "GitHubApiError",
    "GitHubRateLimitError",
    "GitHubAuthError",
    "GitHubNotFoundError",
    # Schemas
    "GitHubUser",
    "GitHubLabel",
    "GitHubMilestone",
    "GitHubReaction",
    "GitHubIssue",
    "GitHubIssueComment",
    "GitHubPullRequest",
    "GitHubPRReview",
    "GitHubCommit",
    "GitHubCommitFile",
    "GitHubRepository",
    "PRFileContext",
    "PRComment",
    # Transformer
    "GitHubTransformer",
    # Service
    "GitHubIngestionService",
    "GithubService",
    # Factory
    "get_github_service",
    "create_github_ingestion_service",
]
