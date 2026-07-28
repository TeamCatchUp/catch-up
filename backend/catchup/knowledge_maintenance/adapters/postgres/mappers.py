from __future__ import annotations

from catchup.db.models import SourceVersion as SourceVersionRow
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion


def to_row(source_version: SourceVersion) -> SourceVersionRow:
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


def to_domain(row: SourceVersionRow) -> SourceVersion:
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
