"""의도: runtime wiring이 connector capability를 구조화된 값으로 다루게 한다."""

from __future__ import annotations

from dataclasses import dataclass

from catchup.connector_core.domain.structure import ConnectorKey


@dataclass(frozen=True)
class RuntimeCapability:
    name: str
    enabled: bool


@dataclass(frozen=True)
class RuntimeRegistration:
    connector: ConnectorKey
    capabilities: tuple[RuntimeCapability, ...]
