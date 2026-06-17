from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.db.models import SourceType
from catchup.db.user_source_mapping import find_user_id_by_source_mapping


class ChannelTalkUserChatAuthorResolver:
    """Resolve Channel Talk manager identifiers to CatchUp user ids for v2 rows."""

    def __init__(self) -> None:
        self._manager_id_cache: dict[str, str | None] = {}

    def resolve_catchup_user_id(
        self,
        db: Session,
        manager_id: str | None,
    ) -> str | None:
        if not manager_id:
            return None

        if manager_id in self._manager_id_cache:
            return self._manager_id_cache[manager_id]

        user_id = find_user_id_by_source_mapping(
            db=db,
            source_type=SourceType.CHANNEL_TALK,
            external_user_identifier=manager_id,
        )
        resolved_id = str(user_id) if user_id is not None else None
        self._manager_id_cache[manager_id] = resolved_id
        return resolved_id
