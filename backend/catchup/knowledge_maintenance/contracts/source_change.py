from __future__ import annotations

from datetime import datetime
from datetime import timezone

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import JsonValue
from pydantic import field_validator
from pydantic import model_validator

from catchup.knowledge_maintenance.domain.source_version import ChangeKind


class SourceIdentityPayload(BaseModel):
    """SourceChangeEnvelope 안의 외부 문서 식별자를 검증한다."""

    model_config = ConfigDict(frozen=True)

    entity_type: str = Field(min_length=1)
    scope_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    external_document_id: str = Field(min_length=1)

    @field_validator(
        "entity_type",
        "scope_id",
        "target_id",
        "external_document_id",
    )
    @classmethod
    def normalize_identity_part(cls, value: str) -> str:
        return _non_blank(value)


class SourceChangeEnvelope(BaseModel):
    """source 변경 생산자가 전달하는 versioned contract를 검증한다."""

    model_config = ConfigDict(frozen=True)

    schema_version: int
    event_id: str = Field(min_length=1)
    workspace_id: int = Field(gt=0)
    source_type: str = Field(min_length=1)
    source_identity: SourceIdentityPayload
    change_kind: ChangeKind
    source_version_key: str = Field(min_length=1)
    title: str | None = None
    canonical_url: str | None = None
    content: str | None
    content_type: str | None
    source_updated_at: datetime | None = None
    observed_at: datetime
    idempotency_key: str = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator(
        "event_id",
        "source_type",
        "source_version_key",
        "idempotency_key",
    )
    @classmethod
    def normalize_required_key(cls, value: str) -> str:
        return _non_blank(value)

    @field_validator("content_type")
    @classmethod
    def normalize_content_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _non_blank(value)

    @field_validator("observed_at", "source_updated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_contract(self) -> SourceChangeEnvelope:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")

        if self.change_kind == ChangeKind.DELETED:
            if self.content is not None or self.content_type is not None:
                raise ValueError(
                    "deleted envelope must not contain content or content_type"
                )
        elif self.content is None or not self.content_type:
            raise ValueError(
                "created or updated envelope requires content and content_type"
            )

        return self


def _non_blank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be blank")
    return normalized
