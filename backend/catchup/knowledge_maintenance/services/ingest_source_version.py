from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from enum import StrEnum

from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.ports.source_versions import SourceVersionUnitOfWork
from catchup.observability.logging import get_logger

logger = get_logger(__name__)


class IngestionResult(StrEnum):
    CREATED = "created"
    DUPLICATE = "duplicate"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class SourceVersionIngestionResult:
    """SourceChangeEnvelope 수집 결과를 표현한다.

    Attributes:
        source_version_id: 생성됐거나 기존인 SourceVersion을 식별한다.
        result: 수집 결과가 created, duplicate, stale 중 무엇인지 나타낸다.
    """

    source_version_id: uuid.UUID
    result: IngestionResult


class SourceVersionPayloadConflict(ValueError):
    """같은 논리적 전달 키가 서로 다른 원천 데이터에 재사용됐음을 나타낸다."""


def ingest_source_change(
    envelope: SourceChangeEnvelope,
    *,
    uow: SourceVersionUnitOfWork,
    id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    clock: Callable[[], datetime] | None = None,
) -> SourceVersionIngestionResult:
    """Envelope 하나를 검증하고 불변 SourceVersion을 최대 하나 저장한다."""

    clock = clock or _utcnow
    source_identity = _to_source_identity(envelope)
    payload_hash = _payload_hash(envelope)

    with uow:
        existing = uow.source_versions.get_by_idempotency_key(
            workspace_id=envelope.workspace_id,
            idempotency_key=envelope.idempotency_key,
        )
        if existing is not None:
            return _resolve_existing(payload_hash, existing)

        existing_version = uow.source_versions.get_by_source_version(
            workspace_id=envelope.workspace_id,
            source_type=envelope.source_type,
            source_identity=source_identity,
            source_version_key=envelope.source_version_key,
        )
        if existing_version is not None:
            return _resolve_existing(payload_hash, existing_version)

        latest = uow.source_versions.get_latest_for_source(
            workspace_id=envelope.workspace_id,
            source_type=envelope.source_type,
            source_identity=source_identity,
        )
        source_version = _build_source_version(
            envelope,
            source_identity=source_identity,
            payload_hash=payload_hash,
            source_version_id=id_factory(),
            created_at=clock(),
        )
        uow.source_versions.add(source_version)
        _ensure_node(source_version.workspace_id, source_version.id, uow)
        uow.commit()
        logger.info(
            "source_version_ingested",
            workspace_id=envelope.workspace_id,
            source_type=envelope.source_type,
            source_version_id=str(source_version.id),
            change_kind=envelope.change_kind.value,
            external_document_id=source_identity.external_document_id,
            source_version_key=envelope.source_version_key,
            stale=_is_stale(envelope, latest),
        )
        return SourceVersionIngestionResult(
            source_version_id=source_version.id,
            result=(
                IngestionResult.STALE
                if _is_stale(envelope, latest)
                else IngestionResult.CREATED
            ),
        )


def _build_source_version(
    envelope: SourceChangeEnvelope,
    *,
    source_identity: SourceIdentity,
    payload_hash: str,
    source_version_id: uuid.UUID,
    created_at: datetime,
) -> SourceVersion:
    return SourceVersion(
        id=source_version_id,
        workspace_id=envelope.workspace_id,
        source_type=envelope.source_type,
        source_identity=source_identity,
        change_kind=envelope.change_kind,
        source_version_key=envelope.source_version_key,
        title=envelope.title,
        canonical_url=envelope.canonical_url,
        content=envelope.content,
        content_type=envelope.content_type,
        content_hash=_content_hash(envelope.content),
        source_updated_at=envelope.source_updated_at,
        observed_at=envelope.observed_at,
        idempotency_key=envelope.idempotency_key,
        payload_hash=payload_hash,
        metadata=dict(envelope.metadata),
        created_at=created_at,
    )


def _resolve_existing(
    payload_hash: str,
    existing: SourceVersion,
) -> SourceVersionIngestionResult:
    if existing.payload_hash != payload_hash:
        logger.warning(
            "source_version_payload_conflict",
            workspace_id=existing.workspace_id,
            source_type=existing.source_type,
            source_version_id=str(existing.id),
            idempotency_key=existing.idempotency_key,
        )
        raise SourceVersionPayloadConflict(
            "the idempotency key or source version was reused with a different payload"
        )
    # 중복 전달은 아무것도 쓰지 않는다. node는 SourceVersion과 같은
    # transaction에서 만들어지므로, 원문이 있으면 node도 반드시 있다.
    return SourceVersionIngestionResult(
        source_version_id=existing.id,
        result=IngestionResult.DUPLICATE,
    )


def _ensure_node(
    workspace_id: int,
    source_version_id: uuid.UUID,
    uow: SourceVersionUnitOfWork,
) -> None:
    """원문을 graph에서 가리킬 수 있게 node identity를 붙인다."""
    uow.knowledge_nodes.ensure_for_resource(
        workspace_id=workspace_id,
        node_kind=NodeKind.SOURCE_VERSION,
        resource_id=source_version_id,
    )


def _is_stale(
    envelope: SourceChangeEnvelope,
    latest: SourceVersion | None,
) -> bool:
    if (
        latest is None
        or envelope.source_updated_at is None
        or latest.source_updated_at is None
    ):
        return False
    return envelope.source_updated_at < latest.source_updated_at


def _to_source_identity(envelope: SourceChangeEnvelope) -> SourceIdentity:
    return SourceIdentity(
        entity_type=envelope.source_identity.entity_type,
        scope_id=envelope.source_identity.scope_id,
        target_id=envelope.source_identity.target_id,
        external_document_id=envelope.source_identity.external_document_id,
    )


def _payload_hash(envelope: SourceChangeEnvelope) -> str:
    # 전달에 딸린 값은 원천 데이터가 아니므로 hash에서 제외한다.
    # 서로 다른 전달도 같은 논리적 SourceVersion으로 식별할 수 있게 한다.
    #
    # `observed_at`이 여기 드는 이유는 그것이 원문의 성질이 아니라 우리가
    # 언제 봤는지이기 때문이다. Poller는 바뀌지 않은 문서를 주기마다 다시
    # 보는데, 이 값이 hash에 들어가면 같은 원문을 다시 본 것만으로
    # SourceVersionPayloadConflict가 난다. 원문이 언제 바뀌었는지는
    # `source_updated_at`이 말하며 그것은 hash에 남는다.
    payload = envelope.model_dump(
        mode="json",
        exclude={"event_id", "idempotency_key", "observed_at"},
    )
    return _stable_hash(payload)


def _content_hash(content: str | None) -> str | None:
    if content is None:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
