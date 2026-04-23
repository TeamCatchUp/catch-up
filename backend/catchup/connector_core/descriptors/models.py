"""의도: connector capability 메타데이터를 타입화해 선언형 registry 구성을 가능하게 한다."""

from __future__ import annotations

from dataclasses import dataclass

from catchup.connector_core.domain.structure import ConnectorBoundary
from catchup.connector_core.domain.structure import ConnectorKey


@dataclass(frozen=True)
class ConnectorRuntimePlan:
    supports_install_auth: bool
    supports_metadata_sync: bool
    supports_full_sync: bool
    supports_incremental: bool
    supports_observability: bool
    targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorDescriptor:
    """Connector 하나의 고정 구조: key + boundary + runtime target plan."""

    key: ConnectorKey
    display_name: str
    boundary: ConnectorBoundary
    runtime: ConnectorRuntimePlan
