from catchup.sync.full.resolvers.confluence import (
    ConfluenceFullSyncTargetResolver,
    get_confluence_full_sync_target_resolver,
)
from catchup.sync.full.resolvers.github import (
    GithubFullSyncTargetResolver,
    get_github_full_sync_target_resolver,
)
from catchup.sync.full.resolvers.jira import (
    JiraFullSyncTargetResolver,
    get_jira_full_sync_target_resolver,
)
from catchup.sync.full.resolvers.slack import (
    SlackFullSyncTargetResolver,
    get_slack_full_sync_target_resolver,
)

__all__ = [
    "ConfluenceFullSyncTargetResolver",
    "GithubFullSyncTargetResolver",
    "JiraFullSyncTargetResolver",
    "SlackFullSyncTargetResolver",
    "get_confluence_full_sync_target_resolver",
    "get_github_full_sync_target_resolver",
    "get_jira_full_sync_target_resolver",
    "get_slack_full_sync_target_resolver",
]
