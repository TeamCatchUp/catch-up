from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from catchup.db.models import KnowledgeNode as KnowledgeNodeRow
from catchup.db.models import Observation as ObservationRow
from catchup.db.models import SourceVersion as SourceVersionRow
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.domain.knowledge_node import ResourceRef
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion


def source_version_to_row(source_version: SourceVersion) -> SourceVersionRow:
    """도메인 SourceVersion을 저장할 row로 바꾼다."""
    return SourceVersionRow(
        id=source_version.id,
        workspace_id=source_version.workspace_id,
        source_type=source_version.source_type,
        entity_type=source_version.source_identity.entity_type,
        scope_id=source_version.source_identity.scope_id,
        target_id=source_version.source_identity.target_id,
        external_document_id=source_version.source_identity.external_document_id,
        change_kind=source_version.change_kind.value,
        source_version_key=source_version.source_version_key,
        title=source_version.title,
        canonical_url=source_version.canonical_url,
        content=source_version.content,
        content_type=source_version.content_type,
        content_hash=source_version.content_hash,
        source_updated_at=source_version.source_updated_at,
        observed_at=source_version.observed_at,
        idempotency_key=source_version.idempotency_key,
        payload_hash=source_version.payload_hash,
        source_metadata=dict(source_version.metadata),
        created_at=source_version.created_at,
    )


def source_version_to_domain(row: SourceVersionRow) -> SourceVersion:
    """저장된 row를 도메인 SourceVersion으로 되돌린다."""
    return SourceVersion(
        id=row.id,
        workspace_id=row.workspace_id,
        source_type=row.source_type,
        source_identity=SourceIdentity(
            entity_type=row.entity_type,
            scope_id=row.scope_id,
            target_id=row.target_id,
            external_document_id=row.external_document_id,
        ),
        change_kind=ChangeKind(row.change_kind),
        source_version_key=row.source_version_key,
        title=row.title,
        canonical_url=row.canonical_url,
        content=row.content,
        content_type=row.content_type,
        content_hash=row.content_hash,
        source_updated_at=row.source_updated_at,
        observed_at=row.observed_at,
        idempotency_key=row.idempotency_key,
        payload_hash=row.payload_hash,
        metadata=row.source_metadata,
        created_at=row.created_at,
    )


def observation_to_row(
    *,
    observation_id: uuid.UUID,
    workspace_id: int,
    source_version_id: uuid.UUID,
    observation: NormalizedObservation,
) -> ObservationRow:
    """정규화 결과를 저장할 row로 바꾼다.

    `NormalizedObservation`은 저장 식별자를 담지 않으므로 여기서 붙인다.
    """
    return ObservationRow(
        id=observation_id,
        workspace_id=workspace_id,
        source_version_id=source_version_id,
        observation_kind=observation.observation_kind.value,
        normalized_content=observation.content,
        normalized_content_hash=observation.content_hash,
        normalizer_id=observation.normalizer_id,
        normalizer_version=observation.normalizer_version,
        source_attributes=dict(observation.source_attributes),
        observation_metadata_entities=[
            _metadata_entity_to_json(entity)
            for entity in observation.metadata_entities
        ],
        observation_metadata={},
        occurred_at=observation.occurred_at,
    )


def observation_to_domain(row: ObservationRow) -> StoredObservation:
    """저장된 row를 도메인 Observation으로 되돌린다."""
    return StoredObservation(
        id=row.id,
        workspace_id=row.workspace_id,
        source_version_id=row.source_version_id,
        observation=NormalizedObservation(
            normalizer_id=row.normalizer_id,
            normalizer_version=row.normalizer_version,
            observation_kind=ObservationKind(row.observation_kind),
            content=row.normalized_content,
            content_hash=row.normalized_content_hash,
            source_attributes=row.source_attributes,
            metadata_entities=tuple(
                _metadata_entity_to_domain(item)
                for item in row.observation_metadata_entities
            ),
            occurred_at=row.occurred_at,
        ),
        created_at=row.created_at,
    )


def _metadata_entity_to_json(entity: MetadataEntity) -> dict[str, Any]:
    """MetadataEntity를 JSONB에 담을 형태로 바꾼다."""
    return {
        "entity_type": entity.entity_type,
        "external_key": entity.external_key,
        "display_name": entity.display_name,
        "attributes": dict(entity.attributes),
    }


def _metadata_entity_to_domain(payload: Mapping[str, Any]) -> MetadataEntity:
    """JSONB에 담긴 항목을 MetadataEntity로 되돌린다."""
    return MetadataEntity(
        entity_type=payload["entity_type"],
        external_key=payload.get("external_key"),
        display_name=payload["display_name"],
        attributes=payload.get("attributes") or {},
    )


def knowledge_node_to_domain(row: KnowledgeNodeRow) -> KnowledgeNode:
    """저장된 row를 도메인 KnowledgeNode로 되돌린다."""
    resource = None
    if row.resource_type is not None and row.resource_id is not None:
        resource = ResourceRef(
            resource_type=row.resource_type,
            resource_id=row.resource_id,
        )

    return KnowledgeNode(
        id=row.id,
        workspace_id=row.workspace_id,
        node_kind=NodeKind(row.node_kind),
        resource=resource,
        entity_type=row.entity_type,
        canonical_key=row.canonical_key,
        display_name=row.display_name,
        lifecycle_state=NodeLifecycleState(row.lifecycle_state),
        merged_into_node_id=row.merged_into_node_id,
        attributes=row.attributes,
        created_at=row.created_at,
    )


def knowledge_node_to_row(node: KnowledgeNode) -> KnowledgeNodeRow:
    """도메인 KnowledgeNode를 저장할 row로 바꾼다."""
    return KnowledgeNodeRow(
        id=node.id,
        workspace_id=node.workspace_id,
        node_kind=node.node_kind.value,
        resource_type=node.resource.resource_type if node.resource else None,
        resource_id=node.resource.resource_id if node.resource else None,
        entity_type=node.entity_type,
        canonical_key=node.canonical_key,
        display_name=node.display_name,
        lifecycle_state=node.lifecycle_state.value,
        merged_into_node_id=node.merged_into_node_id,
        attributes=dict(node.attributes),
    )
