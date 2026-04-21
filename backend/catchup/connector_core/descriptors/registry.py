from __future__ import annotations

from collections.abc import Iterable

from catchup.connector_core.descriptors.models import ConnectorDescriptor
from catchup.connector_core.domain.structure import ConnectorKey


class ConnectorDescriptorRegistry:
    """connector descriptor 조회 경로를 registry 하나로 통일한다."""

    def __init__(self, descriptors: Iterable[ConnectorDescriptor]) -> None:
        self._descriptors = {descriptor.key: descriptor for descriptor in descriptors}

    def get(self, key: ConnectorKey) -> ConnectorDescriptor:
        return self._descriptors[key]

    def list(self) -> tuple[ConnectorDescriptor, ...]:
        return tuple(self._descriptors.values())
