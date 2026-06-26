from __future__ import annotations

from datetime import datetime
from datetime import timezone

from langchain_core.documents import Document

from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticlePreparedDocument,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleAuthorMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleData,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticlePublicationMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleTaxonomyMetadata,
)
from catchup.sync.ingestion.vector_records.channel_talk_document_article import (
    ChannelTalkDocumentArticleVectorRecord,
)


class ChannelTalkDocumentArticleV2RecordMapper:
    """Build v2 vector-store records from prepared Channel Talk article chunks."""

    def to_document(
        self,
        prepared: ChannelTalkArticlePreparedDocument,
        *,
        content: str | None = None,
        document_id: str | None = None,
        internal_author_id: str | None = None,
        synced_at: datetime | None = None,
    ) -> Document:
        return self.to_record(
            prepared,
            content=content,
            document_id=document_id,
            embedding=[],
            internal_author_id=internal_author_id,
            synced_at=synced_at,
        ).to_document()

    def to_record(
        self,
        prepared: ChannelTalkArticlePreparedDocument,
        *,
        content: str | None = None,
        document_id: str | None = None,
        embedding: list[float],
        internal_author_id: str | None = None,
        synced_at: datetime | None = None,
    ) -> ChannelTalkDocumentArticleVectorRecord:
        logical = prepared.logical_metadata
        base = logical.base
        core = logical.document_article_core
        article = core.article
        space = core.space
        author = core.author
        taxonomy = core.taxonomy
        publication = core.publication

        content_value = content if content is not None else prepared.page_content
        body = _text_or_empty(prepared.chunk_body_text)
        record_id = article.article_id
        scope_id = space.channel_id
        target_id = space.space_id
        title = _text_or_empty(article.title)
        url = _first_text(
            base.url,
            article.url,
            _build_internal_article_url(
                channel_id=scope_id,
                space_id=target_id,
                article_id=record_id,
            ),
        )
        created_at = publication.created_at or base.created_at or _now_utc()
        updated_at = publication.updated_at or base.updated_at or created_at

        return ChannelTalkDocumentArticleVectorRecord(
            langchain_id=document_id or prepared.document_id,
            content=content_value,
            embedding=embedding,
            source="channel_talk",
            entity_type="document_article",
            record_id=record_id,
            scope_type="channel",
            scope_id=scope_id,
            target_type="document_space",
            target_id=target_id,
            target_name=_text_or_empty(space.space_name),
            internal_author_id=internal_author_id,
            title=title,
            body=body,
            data=ChannelTalkDocumentArticleData(),
            url=url,
            created_at=created_at,
            updated_at=updated_at,
            synced_at=synced_at or base.synced_at,
            channel_talk_document_article=ChannelTalkDocumentArticleMetadata(
                author=ChannelTalkDocumentArticleAuthorMetadata(
                    external_user_id=author.author_id,
                    internal_user_id=internal_author_id,
                ),
                taxonomy=ChannelTalkDocumentArticleTaxonomyMetadata(
                    topic_ids=list(taxonomy.topic_ids),
                    topic_names=list(taxonomy.topic_names),
                    category_id=taxonomy.category_id,
                    category_name=taxonomy.category_name,
                ),
                publication=ChannelTalkDocumentArticlePublicationMetadata(
                    published_at=publication.published_at,
                    published_revision_id=publication.published_revision_id,
                    current_revision_id=publication.current_revision_id,
                ),
            ),
        )


def _first_text(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    raise ValueError("expected at least one non-empty text value")


def _text_or_empty(value: str | None) -> str:
    return value.strip() if value and value.strip() else ""


def _build_internal_article_url(
    *,
    channel_id: str,
    space_id: str,
    article_id: str,
) -> str:
    return (
        "https://desk.channel.io/#/channels/"
        f"{channel_id}/document_spaces/{space_id}/articles/{article_id}"
    )


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)
