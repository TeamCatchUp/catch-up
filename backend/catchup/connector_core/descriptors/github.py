from __future__ import annotations

from catchup.connector_core.descriptors.models import ConnectorDescriptor
from catchup.connector_core.descriptors.models import ConnectorRuntimePlan
from catchup.connector_core.domain.structure import ConnectorBoundary
from catchup.connector_core.domain.structure import ConnectorKey

GITHUB_DESCRIPTOR = ConnectorDescriptor(
    key=ConnectorKey.GITHUB,
    display_name="GitHub",
    boundary=ConnectorBoundary.TENANT,
    runtime=ConnectorRuntimePlan(
        supports_install_auth=True,
        supports_metadata_sync=True,
        supports_full_sync=True,
        supports_incremental=True,
        supports_observability=True,
        targets=("issue", "pull_request"),
    ),
)
