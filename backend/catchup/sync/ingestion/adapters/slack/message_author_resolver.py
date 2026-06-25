from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.db.models import SourceType
from catchup.db.user_source_mapping import find_user_id_by_source_mapping


class SlackMessageAuthorResolver:
    """Resolve Slack author identifiers to CatchUp user ids for v2 rows."""

    def __init__(self) -> None:
        self._slack_user_id_cache: dict[str, str | None] = {}

    def resolve_catchup_user_id(
        self,
        db: Session,
        slack_user_id: str | None,
    ) -> str | None:
        if not slack_user_id:
            return None

        if slack_user_id in self._slack_user_id_cache:
            return self._slack_user_id_cache[slack_user_id]

        user_id = find_user_id_by_source_mapping(
            db=db,
            source_type=SourceType.SLACK,
            external_user_identifier=slack_user_id,
        )
        resolved_id = str(user_id) if user_id is not None else None
        self._slack_user_id_cache[slack_user_id] = resolved_id
        return resolved_id
