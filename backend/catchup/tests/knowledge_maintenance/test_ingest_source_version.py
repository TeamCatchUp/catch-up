from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime
from datetime import timezone
from types import TracebackType
from typing import Self

import pytest
from pydantic import ValidationError

from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.knowledge_node import resource_ref_for
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository
from catchup.knowledge_maintenance.ports.source_versions import SourceVersionRepository
from catchup.knowledge_maintenance.services.ingest_source_version import IngestionResult
from catchup.knowledge_maintenance.services.ingest_source_version import (
    SourceVersionPayloadConflict,
)
from catchup.knowledge_maintenance.services.ingest_source_version import (
    ingest_source_change,
)

NOW = datetime(2026, 7, 23, 9, 0, tzinfo=timezone.utc)
VERSION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class FakeSourceVersionRepository(SourceVersionRepository):
    def __init__(self) -> None:
        self.items: list[SourceVersion] = []

    def get_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> SourceVersion | None:
        return next(
            (
                item
                for item in self.items
                if item.workspace_id == workspace_id
                and item.idempotency_key == idempotency_key
            ),
            None,
        )

    def get_by_source_version(
        self,
        *,
        workspace_id: int,
        source_type: str,
        source_identity: SourceIdentity,
        source_version_key: str,
    ) -> SourceVersion | None:
        return next(
            (
                item
                for item in self.items
                if item.workspace_id == workspace_id
                and item.source_type == source_type
                and item.source_identity == source_identity
                and item.source_version_key == source_version_key
            ),
            None,
        )

    def get_latest_for_source(
        self,
        *,
        workspace_id: int,
        source_type: str,
        source_identity: SourceIdentity,
    ) -> SourceVersion | None:
        candidates = [
            item
            for item in self.items
            if item.workspace_id == workspace_id
            and item.source_type == source_type
            and item.source_identity == source_identity
        ]
        return max(
            candidates,
            key=lambda item: item.source_updated_at or item.observed_at,
            default=None,
        )

    def add(self, source_version: SourceVersion) -> None:
        self.items.append(source_version)


class FakeKnowledgeNodeRepository(KnowledgeNodeRepository):
    def __init__(self) -> None:
        self.items: list[KnowledgeNode] = []

    def get_for_resource(
        self,
        *,
        workspace_id: int,
        node_kind: NodeKind,
        resource_id: uuid.UUID,
    ) -> KnowledgeNode | None:
        return next(
            (
                item
                for item in self.items
                if item.workspace_id == workspace_id
                and item.node_kind == node_kind
                and item.resource is not None
                and item.resource.resource_id == str(resource_id)
            ),
            None,
        )

    def ensure_for_resource(
        self,
        *,
        workspace_id: int,
        node_kind: NodeKind,
        resource_id: uuid.UUID,
        display_name: str | None = None,
    ) -> KnowledgeNode:
        found = self.get_for_resource(
            workspace_id=workspace_id,
            node_kind=node_kind,
            resource_id=resource_id,
        )
        if found is not None:
            return found

        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind=node_kind,
            resource=resource_ref_for(node_kind, resource_id),
            display_name=display_name,
        )
        self.items.append(node)
        return node


class FakeSourceVersionUnitOfWork:
    def __init__(self) -> None:
        self.source_versions = FakeSourceVersionRepository()
        self.knowledge_nodes = FakeKnowledgeNodeRepository()
        self.committed = False

    def __enter__(self) -> Self:
        self.committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed = True


def _envelope(**overrides: object) -> SourceChangeEnvelope:
    values: dict[str, object] = {
        "schema_version": 1,
        "event_id": "event-1",
        "workspace_id": 1,
        "source_type": "jira",
        "source_identity": {
            "entity_type": "issue",
            "scope_id": "team-catchup",
            "target_id": "CAM",
            "external_document_id": "CAM-180",
        },
        "change_kind": "updated",
        "source_version_key": "38",
        "title": "결제 기능 출시 일정",
        "canonical_url": "https://jira.example.com/browse/CAM-180",
        "content": "결제 기능은 9월 출시 예정이다.",
        "content_type": "text/markdown",
        "source_updated_at": NOW,
        "observed_at": NOW,
        "idempotency_key": "jira:CAM-180:38",
        "metadata": {},
    }
    values.update(overrides)
    return SourceChangeEnvelope.model_validate(values)


def _ingest(
    envelope: SourceChangeEnvelope,
    uow: FakeSourceVersionUnitOfWork,
    *,
    version_id: uuid.UUID = VERSION_ID,
):
    return ingest_source_change(
        envelope,
        uow=uow,
        id_factory=lambda: version_id,
        clock=lambda: NOW,
    )


def test_ingests_new_envelope_as_immutable_source_version() -> None:
    uow = FakeSourceVersionUnitOfWork()

    result = _ingest(_envelope(), uow)

    assert result.result == IngestionResult.CREATED
    assert result.source_version_id == VERSION_ID
    assert uow.committed
    assert len(uow.source_versions.items) == 1
    source_version = uow.source_versions.items[0]
    assert source_version.content_hash is not None
    assert source_version.source_identity.external_document_id == "CAM-180"


def test_same_change_is_returned_as_duplicate_without_another_commit() -> None:
    uow = FakeSourceVersionUnitOfWork()
    first = _envelope()
    _ingest(first, uow)

    retry = first.model_copy(update={"event_id": "event-retry"})
    result = _ingest(retry, uow, version_id=uuid.uuid4())

    assert result.result == IngestionResult.DUPLICATE
    assert result.source_version_id == VERSION_ID
    assert not uow.committed
    assert len(uow.source_versions.items) == 1


def test_same_source_version_with_another_delivery_key_is_duplicate() -> None:
    uow = FakeSourceVersionUnitOfWork()
    _ingest(_envelope(), uow)

    delivered_again = _envelope(
        event_id="event-2",
        idempotency_key="another-delivery-key",
    )
    result = _ingest(delivered_again, uow, version_id=uuid.uuid4())

    assert result.result == IngestionResult.DUPLICATE
    assert result.source_version_id == VERSION_ID
    assert len(uow.source_versions.items) == 1


def test_reused_idempotency_key_with_different_payload_is_rejected() -> None:
    uow = FakeSourceVersionUnitOfWork()
    _ingest(_envelope(), uow)

    changed = _envelope(content="서로 다른 내용")

    with pytest.raises(SourceVersionPayloadConflict):
        _ingest(changed, uow)

    assert len(uow.source_versions.items) == 1


def test_deleted_envelope_creates_tombstone_source_version() -> None:
    uow = FakeSourceVersionUnitOfWork()
    deleted = _envelope(
        change_kind="deleted",
        content=None,
        content_type=None,
    )

    result = _ingest(deleted, uow)

    assert result.result == IngestionResult.CREATED
    tombstone = uow.source_versions.items[0]
    assert tombstone.content is None
    assert tombstone.content_hash is None


def test_older_source_update_is_preserved_but_returned_as_stale() -> None:
    uow = FakeSourceVersionUnitOfWork()
    _ingest(_envelope(), uow)
    older_time = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)
    stale = _envelope(
        event_id="event-old",
        source_version_key="37",
        source_updated_at=older_time,
        observed_at=datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc),
        idempotency_key="jira:CAM-180:37",
    )

    stale_version_id = uuid.uuid4()
    result = _ingest(stale, uow, version_id=stale_version_id)

    assert result.result == IngestionResult.STALE
    assert result.source_version_id == stale_version_id
    assert uow.committed
    assert len(uow.source_versions.items) == 2


def test_same_external_document_in_another_workspace_is_independent() -> None:
    uow = FakeSourceVersionUnitOfWork()
    _ingest(_envelope(), uow)
    other_workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    result = _ingest(
        _envelope(workspace_id=2),
        uow,
        version_id=other_workspace_id,
    )

    assert result.result == IngestionResult.CREATED
    assert result.source_version_id == other_workspace_id
    assert len(uow.source_versions.items) == 2


def test_deleted_envelope_rejects_content() -> None:
    with pytest.raises(ValidationError):
        _envelope(change_kind="deleted")


def test_timestamp_must_include_timezone() -> None:
    with pytest.raises(ValidationError):
        _envelope(observed_at=datetime(2026, 7, 23, 9, 0))


def test_source_identity_rejects_blank_parts() -> None:
    with pytest.raises(ValidationError):
        _envelope(
            source_identity={
                "entity_type": "issue",
                "scope_id": " ",
                "target_id": "CAM",
                "external_document_id": "CAM-180",
            }
        )


def test_source_version_is_immutable_after_contract_conversion() -> None:
    uow = FakeSourceVersionUnitOfWork()
    _ingest(_envelope(metadata={"labels": ["billing"]}), uow)
    source_version = uow.source_versions.items[0]

    with pytest.raises(FrozenInstanceError):
        source_version.title = "변경된 제목"

    with pytest.raises(TypeError):
        source_version.metadata["owner"] = "product"
