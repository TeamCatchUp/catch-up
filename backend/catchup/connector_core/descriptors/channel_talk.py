from __future__ import annotations

from catchup.connector_core.descriptors.models import ConnectorDescriptor
from catchup.connector_core.descriptors.models import ConnectorRuntimePlan
from catchup.connector_core.domain.structure import ConnectorBoundary
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
)

# Channel Talk이 어떤 runtime capability와 logical target을 지원하는지 선언한다.
# 세부 execution stage/user-chat specific ordering은 adapter와 local contract가 소유한다.
CHANNEL_TALK_DESCRIPTOR = ConnectorDescriptor(
    key=ConnectorKey.CHANNEL_TALK,
    display_name="Channel Talk",
    boundary=ConnectorBoundary.TENANT,
    runtime=ConnectorRuntimePlan(
        supports_install_auth=True,
        supports_metadata_sync=True,
        supports_full_sync=True,
        supports_incremental=False,
        supports_observability=False,
        targets=(
            CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
            CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
        ),
    ),
)
