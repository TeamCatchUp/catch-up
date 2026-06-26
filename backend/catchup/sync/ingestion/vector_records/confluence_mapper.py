from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from langchain_core.documents import Document

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.sync.ingestion.document_builders.confluence import ConfluenceV2CommentPart
from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceV2PreparedChunk,
)
from catchup.sync.ingestion.vector_records.confluence import (
    ConfluenceBlogpostVectorRecord,
)
from catchup.sync.ingestion.vector_records.confluence import ConfluenceChunkMetadata
from catchup.sync.ingestion.vector_records.confluence import ConfluenceContentMetadata
from catchup.sync.ingestion.vector_records.confluence import ConfluenceData
from catchup.sync.ingestion.vector_records.confluence import ConfluenceDataPart
from catchup.sync.ingestion.vector_records.confluence import ConfluenceHierarchyMetadata
from catchup.sync.ingestion.vector_records.confluence import ConfluencePageVectorRecord
from catchup.sync.ingestion.vector_records.confluence import ConfluenceSpaceMetadata
from catchup.sync.ingestion.vector_records.confluence import ConfluenceUserMetadata
from catchup.sync.ingestion.vector_records.confluence import ConfluenceVersionMetadata


class ConfluenceV2RecordMapper:
    """Build v2 vector-store records from Confluence prepared chunks."""

    def to_document(
        self,
        prepared: ConfluenceV2PreparedChunk,
        *,
        cloud_id: str,
        content: str | None = None,
        document_id: str | None = None,
        internal_author_id: str | None = None,
        synced_at: datetime | None = None,
    ) -> Document:
        return self.to_record(
            prepared,
            cloud_id=cloud_id,
            content=content,
            document_id=document_id,
            embedding=[],
            internal_author_id=internal_author_id,
            synced_at=synced_at,
        ).to_document()

    def to_record(
        self,
        prepared: ConfluenceV2PreparedChunk,
        *,
        cloud_id: str,
        content: str | None = None,
        document_id: str | None = None,
        embedding: list[float],
        internal_author_id: str | None = None,
        synced_at: datetime | None = None,
    ) -> ConfluencePageVectorRecord | ConfluenceBlogpostVectorRecord:
        created_at = _parse_datetime(prepared.created_at) or _now_utc()
        updated_at = _parse_datetime(prepared.updated_at) or created_at
        target_id = _first_text(prepared.space_key, prepared.space_id, "unknown")
        target_name = _first_text(prepared.space_name, target_id)
        metadata = ConfluenceContentMetadata(
            status=prepared.status,
            space=ConfluenceSpaceMetadata(space_id=prepared.space_id),
            hierarchy=self._hierarchy_metadata(prepared),
            author=self._user_metadata(prepared.author_id, prepared.author_name),
            owner_id=prepared.owner_id,
            version=ConfluenceVersionMetadata(
                number=prepared.version_number,
                author_id=prepared.version_author_id,
                message=prepared.version_message,
                minor_edit=prepared.version_minor_edit,
            ),
            labels=list(prepared.labels),
            chunk=ConfluenceChunkMetadata(
                chunk_index=prepared.chunk_index,
                chunk_count=prepared.chunk_count,
                section_hierarchy=list(prepared.section_hierarchy),
                has_images=prepared.has_images,
                image_urls=list(prepared.image_urls),
            ),
        )
        base_values = {
            "langchain_id": document_id or prepared.document_id,
            "content": content if content is not None else prepared.page_content,
            "embedding": embedding,
            "source": "confluence",
            "entity_type": prepared.entity_type,
            "record_id": prepared.content_id,
            "scope_type": "cloud",
            "scope_id": cloud_id,
            "target_type": "space",
            "target_id": target_id,
            "target_name": target_name,
            "internal_author_id": internal_author_id,
            "title": _first_text(prepared.title, prepared.content_id),
            "body": _text_or_empty(prepared.body_text),
            "data": ConfluenceData(parts=self._parts(prepared.comments)),
            "url": _first_text(
                prepared.url,
                f"confluence:{prepared.entity_type}:{prepared.content_id}",
            ),
            "created_at": created_at,
            "updated_at": updated_at,
            "synced_at": synced_at or _now_utc(),
        }
        if prepared.entity_type == "page":
            return ConfluencePageVectorRecord(
                **base_values,
                confluence_page=metadata,
            )
        if prepared.entity_type == "blogpost":
            return ConfluenceBlogpostVectorRecord(
                **base_values,
                confluence_blogpost=metadata,
            )
        raise ValueError(f"unsupported Confluence entity_type: {prepared.entity_type}")

    @staticmethod
    def _hierarchy_metadata(
        prepared: ConfluenceV2PreparedChunk,
    ) -> ConfluenceHierarchyMetadata | None:
        if (
            prepared.parent_page_id is None
            and prepared.parent_type is None
            and prepared.position is None
        ):
            return None
        return ConfluenceHierarchyMetadata(
            parent_page_id=prepared.parent_page_id,
            parent_type=prepared.parent_type,
            position=prepared.position,
        )

    @staticmethod
    def _user_metadata(
        account_id: str | None,
        display_name: str | None,
    ) -> ConfluenceUserMetadata | None:
        if account_id is None and display_name is None:
            return None
        return ConfluenceUserMetadata(
            account_id=account_id,
            display_name=display_name,
        )

    @classmethod
    def _parts(
        cls,
        comments: list[ConfluenceV2CommentPart],
    ) -> list[ConfluenceDataPart]:
        return [
            part
            for comment in comments
            if (part := cls._build_part(comment)) is not None
        ]

    @staticmethod
    def _build_part(comment: ConfluenceV2CommentPart) -> ConfluenceDataPart | None:
        text = _text_or_empty(comment.text)
        if not text:
            return None
        return ConfluenceDataPart(
            type=comment.type,
            text=text,
            metadata=_drop_none(
                {
                    "comment_id": comment.comment_id,
                    "status": comment.status,
                    "author_id": comment.author_id,
                    "created_at": comment.created_at,
                    "updated_at": comment.updated_at,
                    "resolution_status": comment.resolution_status,
                    "parent_comment_id": comment.parent_comment_id,
                    "selection": comment.selection,
                    "inline_marker_ref": comment.inline_marker_ref,
                    "selection_start": comment.selection_start,
                    "selection_end": comment.selection_end,
                    "match_method": comment.match_method,
                }
            ),
        )


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_atlassian_datetime(value)
    if parsed is not None:
        return parsed
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first_text(*values: str | None) -> str:
    for value in values:
        normalized = _text_or_empty(value)
        if normalized:
            return normalized
    raise ValueError("expected at least one non-empty text value")


def _text_or_empty(value: str | None) -> str:
    return value.strip() if value and value.strip() else ""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)
