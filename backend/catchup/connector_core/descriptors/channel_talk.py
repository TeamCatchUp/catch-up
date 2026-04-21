from __future__ import annotations

from catchup.connector_core.descriptors.models import ConnectorDescriptor
from catchup.connector_core.descriptors.models import ConnectorRuntimePlan
from catchup.connector_core.descriptors.models import ConnectorTargetPlan
from catchup.connector_core.domain.structure import ConnectorBoundary
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.domain.structure import ConnectorStage

# Channel Talk이 어떤 runtime capability와 동기화 stage를 지원하는지 선언해 이후 registry/UI/worker wiring에서 동일한 메타데이터를 재사용한다.
CHANNEL_TALK_DESCRIPTOR = ConnectorDescriptor(
    key=ConnectorKey.CHANNEL_TALK,
    display_name="Channel Talk",
    boundary=ConnectorBoundary.TENANT,
    runtime=ConnectorRuntimePlan(
        supports_install_auth=True,
        supports_metadata_sync=True,
        supports_full_sync=False,
        supports_incremental=False,
        supports_observability=False,
        targets=(
            ConnectorTargetPlan(
                target="user_chat",
                stages=(
                    ConnectorStage.METADATA,
                    ConnectorStage.USER_CHAT_LIST,
                    ConnectorStage.MESSAGE,
                ),
            ),
        ),
    ),
)
