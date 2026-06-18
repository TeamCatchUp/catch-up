from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.db.models import SourceType
from catchup.db.user_source_mapping import find_user_id_by_source_mapping


class JiraIssueAssigneeResolver:
    """Resolve Jira assignee account ids to CatchUp user ids for v2 rows."""

    def __init__(self) -> None:
        self._account_id_cache: dict[str, str | None] = {}

    def resolve_catchup_user_id(
        self,
        db: Session,
        account_id: str | None,
    ) -> str | None:
        if not account_id:
            return None

        if account_id in self._account_id_cache:
            return self._account_id_cache[account_id]

        user_id = find_user_id_by_source_mapping(
            db=db,
            source_type=SourceType.JIRA,
            external_user_identifier=account_id,
        )
        resolved_id = str(user_id) if user_id is not None else None
        self._account_id_cache[account_id] = resolved_id
        return resolved_id
