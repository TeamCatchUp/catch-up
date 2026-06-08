# ruff: noqa: I001
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connector_core.document_format import ChannelTalkDocumentArticleLogicalMetadata
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.connectors.channel_talk.full_sync_target_contract import CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
from catchup.connectors.channel_talk.schemas.channel_connection import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas.document_article import ChannelTalkDocumentArticle
from catchup.connectors.channel_talk.schemas.document_article import ChannelTalkDocumentArticleRevisionView
from catchup.connectors.channel_talk.schemas.document_article import ChannelTalkDocumentArticleState
from catchup.connectors.channel_talk.schemas.document_article import ChannelTalkDocumentArticleView
from catchup.connectors.channel_talk.schemas.document_connection import ChannelTalkDocumentCredentialsRecord
from catchup.sync.audit import SyncAuditContext
from catchup.utils.validation import require_text


DEFAULT_ARTICLE_FULL_SYNC_STATES: tuple[ChannelTalkDocumentArticleState, ...] = (
    ChannelTalkDocumentArticleState.PUBLISHED,
    ChannelTalkDocumentArticleState.UNPUBLISHED,
    ChannelTalkDocumentArticleState.DRAFT,
)


class ChannelTalkArticleFullSyncConnection(BaseModel):
    """Documents article full-sync boundary credentials."""

    model_config = ConfigDict(extra="forbid")

    channel_id: str
    space_id: str
    access_key: str
    access_secret: str

    @field_validator("channel_id", "space_id", "access_key", "access_secret")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @classmethod
    def from_credentials_record(
        cls,
        record: ChannelTalkDocumentCredentialsRecord,
    ) -> "ChannelTalkArticleFullSyncConnection":
        return cls(
            channel_id=record.channel_id,
            space_id=record.space_id,
            access_key=require_text(record.access_key, "access_key"),
            access_secret=require_text(record.access_secret, "access_secret"),
        )


class ChannelTalkFetchedArticle(BaseModel):
    """Article summary plus the best available batch/detail payload."""

    model_config = ConfigDict(extra="forbid")

    language: str
    state: ChannelTalkDocumentArticleState | str | None = None
    list_item: ChannelTalkDocumentArticle
    detail: ChannelTalkDocumentArticleView | None = None
    published_revision: ChannelTalkDocumentArticleRevisionView | None = None
    updated_at: datetime | None = None
    published_at: datetime | None = None

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: str) -> str:
        return require_text(value, "language")

    @model_validator(mode="after")
    def _fill_derived_fields(self) -> "ChannelTalkFetchedArticle":
        detail_article = self.detail.article if self.detail is not None else None
        if self.state is None:
            self.state = (
                detail_article.state
                if detail_article is not None
                else self.list_item.state
            )
        if self.updated_at is None:
            self.updated_at = (
                detail_article.updated_at
                if detail_article is not None
                else self.list_item.updated_at
            )
        if self.published_at is None:
            self.published_at = (
                detail_article.published_at
                if detail_article is not None
                else self.list_item.published_at
            )
        return self

    @property
    def article_id(self) -> str:
        return self.list_item.article_id

    @property
    def ordering_timestamp(self) -> datetime | None:
        return self.updated_at or self.published_at


class ChannelTalkFetchedArticlesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundles: tuple[ChannelTalkFetchedArticle, ...] = ()
    fetched_count: int = 0
    article_ids: tuple[str, ...] = ()
    next_checkpoint_state: ChannelTalkDocumentArticleState | None = None
    next_checkpoint_cursor: str | None = None

    @field_validator("article_ids")
    @classmethod
    def _validate_article_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(require_text(item, "article_ids") for item in value)

    @model_validator(mode="after")
    def _validate_checkpoint_and_fill_summary_fields(
        self,
    ) -> "ChannelTalkFetchedArticlesResult":
        if self.fetched_count == 0 and self.bundles:
            self.fetched_count = len(self.bundles)
        if not self.article_ids and self.bundles:
            self.article_ids = tuple(bundle.article_id for bundle in self.bundles)
        if (
            self.next_checkpoint_cursor is not None
            and self.next_checkpoint_state is None
        ):
            raise ValueError(
                "next_checkpoint_state is required with next_checkpoint_cursor"
            )
        return self


class ChannelTalkArticleFullSyncCheckpoint(BaseModel):
    """Article full sync가 다음 실행에서 이어갈 위치를 담는다."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    target: Literal["document_article"] = CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
    space_id: str
    state: ChannelTalkDocumentArticleState | None = None
    next_cursor: str | None = None

    @field_validator("tenant_id", "space_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

# TODO : Credential을 Execution Request에서 전달하지 말고, Article Client Initialization 시점에 가져오도록 수정
class ChannelTalkArticleSyncExecutionRequest(SyncExecutionRequest):
    """Execution request for the Channel Talk Documents article ingestion lane."""

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
    target: Literal["document_article"] = CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
    channel_connection: ChannelTalkCredentialsRecord
    document_connection: ChannelTalkDocumentCredentialsRecord
    checkpoint: ChannelTalkArticleFullSyncCheckpoint | None = None
    audit_context: SyncAuditContext | None = None

    @model_validator(mode="after")
    def _validate_connection_alignment(
        self,
    ) -> "ChannelTalkArticleSyncExecutionRequest":
        if self.channel_connection.channel_id != self.tenant_id:
            raise ValueError("channel_connection.channel_id must match tenant_id")
        if self.document_connection.channel_id != self.tenant_id:
            raise ValueError("document_connection.channel_id must match tenant_id")
        if self.checkpoint is not None and self.checkpoint.tenant_id != self.tenant_id:
            raise ValueError("checkpoint.tenant_id must match tenant_id")
        if (
            self.checkpoint is not None
            and self.checkpoint.space_id != self.document_connection.space_id
        ):
            raise ValueError("checkpoint.space_id must match document space_id")
        if (
            self.checkpoint is not None
            and self.checkpoint.state is not None
            and self.checkpoint.state not in DEFAULT_ARTICLE_FULL_SYNC_STATES
        ):
            raise ValueError("checkpoint.state must be included in fetch states")
        return self

    @property
    def channel_id(self) -> str:
        return self.tenant_id

    @property
    def channel_name(self) -> str:
        return self.channel_connection.channel_name

    @property
    def space_id(self) -> str:
        return self.document_connection.space_id

    @property
    def space_name(self) -> str:
        return self.document_connection.space_name


class ChannelTalkArticleIncrementalExecutionRequest(
    ChannelTalkArticleSyncExecutionRequest
):
    """Exact-refresh execution request for one Channel Talk article."""

    article_id: str

    @field_validator("article_id")
    @classmethod
    def _validate_article_id(cls, value: str) -> str:
        return require_text(value, "article_id")


class ChannelTalkArticleFullSyncFetchResult(BaseModel):
    """Typed fetch result for the Article lane."""

    model_config = ConfigDict(extra="forbid")

    channel_id: str
    space_id: str
    language: str
    bundles: tuple[ChannelTalkFetchedArticle, ...] = ()
    fetched_count: int = 0
    fetched_article_ids: tuple[str, ...] = ()
    next_checkpoint: ChannelTalkArticleFullSyncCheckpoint | None = None

    @field_validator("channel_id", "space_id", "language")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @field_validator("fetched_article_ids")
    @classmethod
    def _validate_article_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(require_text(item, "fetched_article_ids") for item in value)

    @model_validator(mode="after")
    def _validate_summary_alignment(
        self,
    ) -> "ChannelTalkArticleFullSyncFetchResult":
        if self.fetched_count != len(self.bundles):
            raise ValueError("fetched_count must match bundles")
        if self.fetched_article_ids != tuple(
            bundle.article_id for bundle in self.bundles
        ):
            raise ValueError("fetched_article_ids must match bundles")
        return self


class ChannelTalkArticlePreparedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    article_id: str
    page_content: str
    logical_metadata: ChannelTalkDocumentArticleLogicalMetadata
    storage_metadata: dict[str, object]

    @field_validator("document_id", "article_id", "page_content")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @property
    def contextual_content(self) -> str:
        return self.logical_metadata.base.contextual_content


@dataclass(frozen=True)
class ArticlePreparedDocumentPayload:
    document_id: str
    article_id: str
    page_content: str
    logical_metadata: ChannelTalkDocumentArticleLogicalMetadata
    storage_metadata: dict[str, object]


@dataclass(frozen=True)
class ArticleBuildResult:
    documents: list[ArticlePreparedDocumentPayload]
    delete_prefix: str


class ChannelTalkArticleFullSyncTransformResult(BaseModel):
    """Typed transform result for materialized article chunks."""

    model_config = ConfigDict(extra="forbid")

    documents: tuple[ChannelTalkArticlePreparedDocument, ...] = ()
    delete_prefixes: tuple[str, ...] = ()
    prepared_document_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _fill_prepared_document_ids(
        self,
    ) -> "ChannelTalkArticleFullSyncTransformResult":
        if not self.prepared_document_ids and self.documents:
            self.prepared_document_ids = tuple(
                document.document_id for document in self.documents
            )
        return self


class ChannelTalkArticleFullSyncSummaryResult(BaseModel):
    """Typed summary placeholder; article summarization is added in a later slice."""

    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False
    document_count: int = 0


class ChannelTalkArticleFullSyncPersistResult(BaseModel):
    """Persist result for article chunk materialization."""

    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    persisted_ids: tuple[str, ...] = ()
    deleted_prefixes: tuple[str, ...] = ()


class ChannelTalkArticleSyncExecutionResult(SyncExecutionResult):
    """Final typed result for an Article ingestion run."""

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
    target: Literal["document_article"] = CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
    collected_count: int = 0
    document_count: int = 0
    fetched: ChannelTalkArticleFullSyncFetchResult
    transformed: ChannelTalkArticleFullSyncTransformResult
    summary: ChannelTalkArticleFullSyncSummaryResult
    persisted: ChannelTalkArticleFullSyncPersistResult

    @property
    def channel_id(self) -> str:
        return self.tenant_id

    @property
    def space_id(self) -> str:
        return self.fetched.space_id


class ChannelTalkArticleIncrementalExecutionResult(
    ChannelTalkArticleSyncExecutionResult
):
    """Final typed result for one article exact-refresh run."""


ChannelTalkArticleFullSyncExecutionRequest = ChannelTalkArticleSyncExecutionRequest
ChannelTalkArticleFullSyncExecutionResult = ChannelTalkArticleSyncExecutionResult
