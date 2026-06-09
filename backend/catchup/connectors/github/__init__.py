"""
Github Connector

Github 데이터 수집 및 PGVector 적재를 위한 커넥터.

주요 컴포넌트:
- GitHubApiClient: Github REST API 클라이언트
- GithubTransformer: API 응답 → LangChain Document 변환
- GithubIngestionService: 데이터 동기화 서비스
"""

from catchup.connectors.github.client import (
    GitHubApiClient,
    GitHubApiError,
    GitHubRateLimitError,
    GitHubAuthError,
    GitHubNotFoundError,
)
from catchup.connectors.github.schemas import (
    GithubUser,
    GithubIssue,
    GithubIssueComment,
    GithubPullRequest,
    GithubPRReview,
    GithubCommit,
    GithubCommitFile,
    GithubRepository,
    PRFileContext,
    PRComment,
)
from catchup.sync.ingestion.document_builders.github import GithubTransformer
from catchup.connectors.github.auth import (
    GitHubAppService,
    get_github_app_service,
)
# Note: service, factory는 순환 import 방지를 위해 직접 import 필요
# from catchup.connectors.github.service import GithubIngestionService

__all__ = [
    # Client
    "GitHubApiClient",
    "GitHubApiError",
    "GitHubRateLimitError",
    "GitHubAuthError",
    "GitHubNotFoundError",
    # Schemas
    "GithubUser",
    "GithubIssue",
    "GithubIssueComment",
    "GithubPullRequest",
    "GithubPRReview",
    "GithubCommit",
    "GithubCommitFile",
    "GithubRepository",
    "PRFileContext",
    "PRComment",
    # Transformer
    "GithubTransformer",
    # Auth
    "GitHubAppService",
    "get_github_app_service",
]
