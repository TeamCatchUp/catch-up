from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.db.models import SourceType
from catchup.db.user_source_mapping import find_user_id_by_source_mapping


class ChannelTalkArticleAuthorResolver:
    """Resolve Channel Talk document author identifiers to CatchUp user ids."""

    def __init__(self) -> None:
        self._author_id_cache: dict[str, str | None] = {}

    def resolve_catchup_user_id(
        self,
        db: Session,
        author_id: str | None,
    ) -> str | None:
        if not author_id:
            return None

        if author_id in self._author_id_cache:
            return self._author_id_cache[author_id]

        user_id = find_user_id_by_source_mapping(
            db=db,
            source_type=SourceType.CHANNEL_TALK,
            external_user_identifier=author_id,
        )
        resolved_id = str(user_id) if user_id is not None else None
        self._author_id_cache[author_id] = resolved_id
        return resolved_id
