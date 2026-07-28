from __future__ import annotations

import hashlib

from catchup.db.models import SourceVersionRow
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion


def source_identity_hash(source_identity: SourceIdentity) -> str:
    """복합 identity를 UNIQUE index가 쓸 고정 길이 키로 만든다."""
    parts = "\x1f".join(
        (
            source_identity.entity_type,
            source_identity.scope_id,
            source_identity.target_id,
            source_identity.external_document_id,
        )
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def to_row(source_version: SourceVersion) -> SourceVersionRow:
    """도메인 SourceVersion을 저장할 row로 바꾼다."""
    return SourceVersionRow(
        id=source_version.id,
        workspace_id=source_version.workspace_id,
        source_type=source_version.source_type,
        source_entity_type=source_version.source_identity.entity_type,
        source_scope_id=source_version.source_identity.scope_id,
        source_target_id=source_version.source_identity.target_id,
        source_external_document_id=(
            source_version.source_identity.external_document_id
        ),
        source_identity_hash=source_identity_hash(source_version.source_identity),
        source_version_key=source_version.source_version_key,
        change_kind=source_version.change_kind.value,
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
            entity_type=row.source_entity_type,
            scope_id=row.source_scope_id,
            target_id=row.source_target_id,
            external_document_id=row.source_external_document_id,
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
