from catchup.sync.full.resolvers.channel_talk_full_sync_resolver import (
    ChannelTalkFullSyncTargetResolver,
)
from catchup.sync.full.resolvers.channel_talk_full_sync_resolver import (
    get_channel_talk_full_sync_target_resolver,
)
from catchup.sync.full.resolvers.confluence import ConfluenceFullSyncTargetResolver
from catchup.sync.full.resolvers.confluence import (
    get_confluence_full_sync_target_resolver,
)
from catchup.sync.full.resolvers.github import GithubFullSyncTargetResolver
from catchup.sync.full.resolvers.github import get_github_full_sync_target_resolver
from catchup.sync.full.resolvers.jira import JiraFullSyncTargetResolver
from catchup.sync.full.resolvers.jira import get_jira_full_sync_target_resolver
from catchup.sync.full.resolvers.slack import SlackFullSyncTargetResolver
from catchup.sync.full.resolvers.slack import get_slack_full_sync_target_resolver

__all__ = [
    "ChannelTalkFullSyncTargetResolver",
    "ConfluenceFullSyncTargetResolver",
    "GithubFullSyncTargetResolver",
    "JiraFullSyncTargetResolver",
    "SlackFullSyncTargetResolver",
    "get_channel_talk_full_sync_target_resolver",
    "get_confluence_full_sync_target_resolver",
    "get_github_full_sync_target_resolver",
    "get_jira_full_sync_target_resolver",
    "get_slack_full_sync_target_resolver",
]
