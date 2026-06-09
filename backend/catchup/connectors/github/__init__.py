"""
Github Connector

Github vendor API primitive.

주요 컴포넌트:
- GitHubApiClient: Github REST API 클라이언트
"""

from catchup.connectors.github.auth import GitHubAppService
from catchup.connectors.github.auth import get_github_app_service
from catchup.connectors.github.client import GitHubApiClient
from catchup.connectors.github.client import GitHubApiError
from catchup.connectors.github.client import GitHubAuthError
from catchup.connectors.github.client import GitHubNotFoundError
from catchup.connectors.github.client import GitHubRateLimitError
from catchup.connectors.github.schemas import GithubCommit
from catchup.connectors.github.schemas import GithubCommitFile
from catchup.connectors.github.schemas import GithubIssue
from catchup.connectors.github.schemas import GithubIssueComment
from catchup.connectors.github.schemas import GithubPRReview
from catchup.connectors.github.schemas import GithubPullRequest
from catchup.connectors.github.schemas import GithubRepository
from catchup.connectors.github.schemas import GithubUser
from catchup.connectors.github.schemas import PRComment
from catchup.connectors.github.schemas import PRFileContext

__all__ = [
    # Client
    "GitHubApiClient",
    "GitHubAuthError",
    "GitHubApiError",
    "GitHubNotFoundError",
    "GitHubRateLimitError",
    # Schemas
    "GithubCommit",
    "GithubCommitFile",
    "GithubIssue",
    "GithubIssueComment",
    "GithubRepository",
    "GithubPullRequest",
    "GithubPRReview",
    "GithubUser",
    "PRComment",
    "PRFileContext",
    # Auth
    "GitHubAppService",
    "get_github_app_service",
]
