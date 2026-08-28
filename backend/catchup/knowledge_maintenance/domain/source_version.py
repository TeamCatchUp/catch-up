from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from types import MappingProxyType

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


class ChangeKind(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """외부 source 문서 하나를 안정적으로 식별한다.

    Attributes:
        entity_type: 외부 source에서 문서가 어떤 종류인지 나타낸다.
        scope_id: connector 설치나 team처럼 문서가 속한 접근 범위를 식별한다.
        target_id: project나 channel처럼 scope 안의 수집 대상을 식별한다.
        external_document_id: 외부 source에서 문서 한 건을 식별한다.
    """

    entity_type: str
    scope_id: str
    target_id: str
    external_document_id: str

    def __post_init__(self) -> None:
        for field_name in (
            "entity_type",
            "scope_id",
            "target_id",
            "external_document_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_blank(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True, slots=True)
class SourceVersion:
    """Knowledge Maintenance가 소유하는 불변 원문 버전을 표현한다.

    Attributes:
        id: CatchUp 내부에서 SourceVersion 한 건을 식별한다.
        workspace_id: SourceVersion이 속한 CatchUp workspace를 식별한다.
        source_type: jira나 slack처럼 원문이 유입된 source 종류를 나타낸다.
        source_identity: 외부 source 문서 한 건의 복합 identity를 보존한다.
        change_kind: 원문이 생성, 수정, 삭제 중 어떤 변경인지 나타낸다.
        source_version_key: 외부 source가 부여한 버전 식별자를 보존한다.
        title: 사람이 원문을 알아볼 수 있는 제목을 보존한다.
        canonical_url: 사람이 외부 source의 원문을 열 주소를 보존한다.
        content: 해당 버전에서 관찰한 원문 전체 내용을 보존한다.
        content_type: content의 MIME type이나 표현 형식을 나타낸다.
        content_hash: content의 동일 여부를 비교하는 hash를 나타낸다.
        source_updated_at: 외부 source에서 원문이 변경된 시각을 나타낸다.
        observed_at: Poller가 해당 원문 상태를 관찰한 시각을 나타낸다.
        idempotency_key: 같은 변경의 중복 저장을 막는 전달 키를 보존한다.
        payload_hash: 전달 식별자를 제외한 Envelope의 hash를 나타낸다.
        metadata: source별 부가 정보를 JSON 호환 형태로 보존한다.
        created_at: CatchUp이 SourceVersion record를 만든 시각을 나타낸다.
    """

    id: uuid.UUID
    workspace_id: int
    source_type: str
    source_identity: SourceIdentity
    change_kind: ChangeKind
    source_version_key: str
    title: str | None
    canonical_url: str | None
    content: str | None
    content_type: str | None
    content_hash: str | None
    source_updated_at: datetime | None
    observed_at: datetime
    idempotency_key: str
    payload_hash: str
    metadata: Mapping[str, JsonValue]
    created_at: datetime

    def __post_init__(self) -> None:
        if self.workspace_id <= 0:
            raise ValueError("workspace_id must be greater than 0")

        for field_name in (
            "source_type",
            "source_version_key",
            "idempotency_key",
            "payload_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_blank(getattr(self, field_name), field_name),
            )

        object.__setattr__(
            self,
            "observed_at",
            _to_utc(self.observed_at, "observed_at"),
        )
        object.__setattr__(
            self,
            "created_at",
            _to_utc(self.created_at, "created_at"),
        )
        if self.source_updated_at is not None:
            object.__setattr__(
                self,
                "source_updated_at",
                _to_utc(self.source_updated_at, "source_updated_at"),
            )

        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

        if self.change_kind == ChangeKind.DELETED:
            if self.content is not None or self.content_type is not None:
                raise ValueError(
                    "deleted SourceVersion must not contain content or content_type"
                )
        elif self.content is None or not self.content_type:
            raise ValueError(
                "created or updated SourceVersion requires content and content_type"
            )


def _non_blank(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _to_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return value.astimezone(timezone.utc)
