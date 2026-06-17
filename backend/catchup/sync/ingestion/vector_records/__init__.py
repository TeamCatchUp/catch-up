"""Typed vector-store v2 ingestion records."""

from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleData,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleDataPart,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleVectorRecord,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article_mapper import (
    ChannelTalkDocumentArticleV2RecordMapper,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatData,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatDataPart,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat import (
    ChannelTalkUserChatVectorRecord,
)
from catchup.sync.ingestion.vector_records.channel_talk_user_chat_mapper import (
    ChannelTalkUserChatV2RecordMapper,
)
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueData
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueDataPart
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueMetadata
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueUserMetadata
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueVectorRecord
from catchup.sync.ingestion.vector_records.github_issue_mapper import (
    GithubIssueV2RecordMapper,
)
from catchup.sync.ingestion.vector_records.github_pr import GithubPrData
from catchup.sync.ingestion.vector_records.github_pr import GithubPrDataPart
from catchup.sync.ingestion.vector_records.github_pr import GithubPrMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrUserMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrVectorRecord
from catchup.sync.ingestion.vector_records.github_pr_mapper import (
    GithubPrV2RecordMapper,
)
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueData
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueDataPart
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueMetadata
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueUserMetadata
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueVectorRecord
from catchup.sync.ingestion.vector_records.jira_issue_mapper import (
    JiraIssueV2RecordMapper,
)
from catchup.sync.ingestion.vector_records.slack_message import SlackMessageData
from catchup.sync.ingestion.vector_records.slack_message import SlackMessageDataPart
from catchup.sync.ingestion.vector_records.slack_message import SlackMessageMetadata
from catchup.sync.ingestion.vector_records.slack_message import SlackMessageVectorRecord
from catchup.sync.ingestion.vector_records.slack_message_mapper import (
    SlackMessageV2RecordMapper,
)

__all__ = [
    "ChannelTalkUserChatData",
    "ChannelTalkUserChatDataPart",
    "ChannelTalkUserChatMetadata",
    "ChannelTalkUserChatV2RecordMapper",
    "ChannelTalkUserChatVectorRecord",
    "ChannelTalkDocumentArticleData",
    "ChannelTalkDocumentArticleDataPart",
    "ChannelTalkDocumentArticleMetadata",
    "ChannelTalkDocumentArticleV2RecordMapper",
    "ChannelTalkDocumentArticleVectorRecord",
    "GithubIssueData",
    "GithubIssueDataPart",
    "GithubIssueMetadata",
    "GithubIssueUserMetadata",
    "GithubIssueV2RecordMapper",
    "GithubIssueVectorRecord",
    "GithubPrData",
    "GithubPrDataPart",
    "GithubPrMetadata",
    "GithubPrUserMetadata",
    "GithubPrV2RecordMapper",
    "GithubPrVectorRecord",
    "JiraIssueData",
    "JiraIssueDataPart",
    "JiraIssueMetadata",
    "JiraIssueUserMetadata",
    "JiraIssueV2RecordMapper",
    "JiraIssueVectorRecord",
    "SlackMessageData",
    "SlackMessageDataPart",
    "SlackMessageMetadata",
    "SlackMessageV2RecordMapper",
    "SlackMessageVectorRecord",
]
