"""
Slack Connector

Slack vendor API primitive.
"""

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.connectors.slack.client import SlackRateLimitError
from catchup.connectors.slack.schemas import SlackChannel
from catchup.connectors.slack.schemas import SlackFile
from catchup.connectors.slack.schemas import SlackMessage
from catchup.connectors.slack.schemas import SlackThreadReply
from catchup.connectors.slack.schemas import SlackUser
from catchup.connectors.slack.schemas import SlackUserProfile
from catchup.connectors.slack.schemas import SlackWorkspace

__all__ = [
    "SlackApiClientWrapper",
    "SlackChannel",
    "SlackConnectorApiError",
    "SlackFile",
    "SlackMessage",
    "SlackRateLimitError",
    "SlackThreadReply",
    "SlackUser",
    "SlackUserProfile",
    "SlackWorkspace",
]
