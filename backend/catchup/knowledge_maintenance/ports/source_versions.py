from __future__ import annotations

from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion


class SourceVersionRepository(Protocol):
    """SourceVersion 수집에 필요한 영속성 기능을 정의한다."""

    def get_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> SourceVersion | None: ...

    def get_by_source_version(
        self,
        *,
        workspace_id: int,
        source_type: str,
        source_identity: SourceIdentity,
        source_version_key: str,
    ) -> SourceVersion | None: ...

    def get_latest_for_source(
        self,
        *,
        workspace_id: int,
        source_type: str,
        source_identity: SourceIdentity,
    ) -> SourceVersion | None: ...

    def add(self, source_version: SourceVersion) -> None: ...


class SourceVersionUnitOfWork(Protocol):
    """SourceVersion 수집에 필요한 transaction 경계를 정의한다."""

    source_versions: SourceVersionRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...
