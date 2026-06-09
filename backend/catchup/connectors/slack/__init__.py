"""
Slack Connector

Slack 데이터를 PGVector에 적재하기 위한 커넥터.
"""

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.client import SlackConnectorApiError, SlackRateLimitError
from catchup.connectors.slack.factory import (
    create_slack_ingestion_service,
    create_slack_metadata_service,
)
from catchup.connectors.slack.ingestion_service import SlackIngestionService
from catchup.connectors.slack.metadata_service import SlackMetadataService
from catchup.connectors.slack.schemas import (
    SlackChannel,
    SlackFile,
    SlackMessage,
    SlackThreadReply,
    SlackUser,
    SlackUserProfile,
    SlackWorkspace,
)
from catchup.sync.ingestion.document_builders.slack import SlackTransformer

__all__ = [
    "SlackApiClientWrapper",
    "SlackChannel",
    "SlackConnectorApiError",
    "SlackFile",
    "SlackIngestionService",
    "SlackMetadataService",
    "SlackMessage",
    "SlackRateLimitError",
    "SlackThreadReply",
    "SlackTransformer",
    "SlackUser",
    "SlackUserProfile",
    "SlackWorkspace",
    "create_slack_ingestion_service",
    "create_slack_metadata_service",
]
