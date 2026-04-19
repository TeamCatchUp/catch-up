"""의도: connector capability 메타데이터를 타입화해 선언형 registry 구성을 가능하게 한다."""

from __future__ import annotations

from dataclasses import dataclass

from catchup.connector_core.domain.structure import ConnectorBoundary
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.domain.structure import ConnectorStage


@dataclass(frozen=True)
class ConnectorTargetPlan:
    """Tenant boundary 내부에서 어떤 target을 어떤 stage 순서로 다루는지 설명한다."""

    target: str
    stages: tuple[ConnectorStage, ...]


@dataclass(frozen=True)
class ConnectorRuntimePlan:
    supports_install_auth: bool
    supports_metadata_sync: bool
    supports_full_sync: bool
    supports_incremental: bool
    supports_observability: bool
    targets: tuple[ConnectorTargetPlan, ...] = ()


@dataclass(frozen=True)
class ConnectorDescriptor:
    """Connector 하나의 고정 구조: key + boundary + runtime target plan."""

    key: ConnectorKey
    display_name: str
    boundary: ConnectorBoundary
    runtime: ConnectorRuntimePlan
