from __future__ import annotations

from catchup.connector_core.descriptors.models import ConnectorDescriptor
from catchup.connector_core.descriptors.models import ConnectorRuntimePlan
from catchup.connector_core.domain.structure import ConnectorBoundary
from catchup.connector_core.domain.structure import ConnectorKey

SLACK_DESCRIPTOR = ConnectorDescriptor(
    key=ConnectorKey.SLACK,
    display_name="Slack",
    boundary=ConnectorBoundary.TENANT,
    runtime=ConnectorRuntimePlan(
        supports_install_auth=True,
        supports_metadata_sync=True,
        supports_full_sync=True,
        supports_incremental=True,
        supports_observability=True,
        targets=("message",),
    ),
)
