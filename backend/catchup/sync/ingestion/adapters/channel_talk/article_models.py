from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connectors.channel_talk.document_space.article_fetch_models import (
    DEFAULT_ARTICLE_FULL_SYNC_STATES,
)
from catchup.connectors.channel_talk.document_space.article_fetch_models import (
    ChannelTalkArticleFullSyncConnection as ChannelTalkArticleFullSyncConnection,
)
from catchup.connectors.channel_talk.document_space.article_fetch_models import (
    ChannelTalkFetchedArticle,
)
from catchup.connectors.channel_talk.document_space.article_fetch_models import (
    ChannelTalkFetchedArticlesResult as ChannelTalkFetchedArticlesResult,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleState,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.document_format import (
    ChannelTalkDocumentArticleLogicalMetadata,
)
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.utils.validation import require_text


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

    connector: Literal[SyncConnector.CHANNEL_TALK] = SyncConnector.CHANNEL_TALK
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
    failed_article_ids: tuple[str, ...] = ()
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
    chunk_body_text: str
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
    chunk_body_text: str
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
    delete_record_ids: tuple[str, ...] = ()
    prepared_document_ids: tuple[str, ...] = ()
    v2_documents: tuple[Document, ...] = ()
    v2_failed_ids: tuple[str, ...] = ()

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
    v2_documents: tuple[Document, ...] = ()


class ChannelTalkArticleFullSyncPersistResult(BaseModel):
    """Persist result for article chunk materialization."""

    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    persisted_ids: tuple[str, ...] = ()
    deleted_prefixes: tuple[str, ...] = ()
    v2_error_count: int = 0
    v2_failed_ids: tuple[str, ...] = ()


class ChannelTalkArticleSyncExecutionResult(SyncExecutionResult):
    """Final typed result for an Article ingestion run."""

    connector: Literal[SyncConnector.CHANNEL_TALK] = SyncConnector.CHANNEL_TALK
    target: Literal["document_article"] = CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
    collected_count: int = 0
    document_count: int = 0
    fetched: ChannelTalkArticleFullSyncFetchResult
    transformed: ChannelTalkArticleFullSyncTransformResult
    summary: ChannelTalkArticleFullSyncSummaryResult
    persisted: ChannelTalkArticleFullSyncPersistResult
    v2_failed_count: int = 0
    v2_failed_ids: tuple[str, ...] = ()

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


class ChannelTalkArticleV2BackfillSeed(BaseModel):
    """v1 row values preserved while hydrating Channel Talk Article v2 metadata."""

    model_config = ConfigDict(extra="forbid")

    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]

    @field_validator("langchain_id", "record_id", "content")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")


class ChannelTalkArticleV2BackfillExecutionRequest(
    ChannelTalkArticleSyncExecutionRequest
):
    """Hydrate v1 Article rows into v2 without changing legacy storage."""

    target: Literal["document_article_v2_backfill"] = "document_article_v2_backfill"
    seeds: tuple[ChannelTalkArticleV2BackfillSeed, ...] = ()


class ChannelTalkArticleV2BackfillExecutionResult(ChannelTalkArticleSyncExecutionResult):
    """Final typed result for Article v2 backfill batches."""

    target: Literal["document_article_v2_backfill"] = "document_article_v2_backfill"


ChannelTalkArticleFullSyncExecutionRequest = ChannelTalkArticleSyncExecutionRequest
ChannelTalkArticleFullSyncExecutionResult = ChannelTalkArticleSyncExecutionResult
