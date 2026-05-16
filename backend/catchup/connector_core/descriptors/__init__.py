from catchup.connector_core.descriptors.channel_talk import CHANNEL_TALK_DESCRIPTOR
from catchup.connector_core.descriptors.confluence import CONFLUENCE_DESCRIPTOR
from catchup.connector_core.descriptors.github import GITHUB_DESCRIPTOR
from catchup.connector_core.descriptors.models import ConnectorDescriptor
from catchup.connector_core.descriptors.models import ConnectorRuntimePlan
from catchup.connector_core.descriptors.registry import ConnectorDescriptorRegistry
from catchup.connector_core.descriptors.slack import SLACK_DESCRIPTOR

__all__ = [
    "CHANNEL_TALK_DESCRIPTOR",
    "CONFLUENCE_DESCRIPTOR",
    "ConnectorDescriptor",
    "ConnectorDescriptorRegistry",
    "ConnectorRuntimePlan",
    "GITHUB_DESCRIPTOR",
    "SLACK_DESCRIPTOR",
]
