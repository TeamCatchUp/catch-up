"""
Slack Connector

Slack 데이터를 PGVector에 적재하기 위한 커넥터.
"""

from catchup.components.connectors.slack.client import SlackApiClientWrapper
from catchup.components.connectors.slack.factory import create_slack_ingestion_service
from catchup.components.connectors.slack.schemas import (
    SlackChannel,
    SlackFile,
    SlackMessage,
    SlackThreadReply,
    SlackUser,
    SlackUserProfile,
    SlackWorkspace,
)
from catchup.components.connectors.slack.service import SlackIngestionService
from catchup.components.connectors.slack.transformers import SlackTransformer

__all__ = [
    "SlackApiClientWrapper",
    "SlackChannel",
    "SlackFile",
    "SlackIngestionService",
    "SlackMessage",
    "SlackThreadReply",
    "SlackTransformer",
    "SlackUser",
    "SlackUserProfile",
    "SlackWorkspace",
    "create_slack_ingestion_service",
]
