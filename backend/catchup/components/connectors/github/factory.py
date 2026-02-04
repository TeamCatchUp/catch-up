from functools import lru_cache

from catchup.components.connectors.github.service import GithubService


@lru_cache(maxsize=1)
def get_github_service() -> GithubService:
    return GithubService()
