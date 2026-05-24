from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timezone
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.connectors.slack.client import SlackRateLimitError
from catchup.db.engine import SessionLocal
from catchup.db.models import SlackChannel
from catchup.db.models import SlackOAuthToken
from catchup.db.models import SlackUser
from catchup.db.models import SlackWorkspace
from catchup.db.models import SourceType
from catchup.db.slack.domain_repository import get_channel
from catchup.db.slack.domain_repository import get_users_by_ids
from catchup.db.slack.domain_repository import get_workspace
from catchup.db.slack.oauth_repository import get_slack_token_by_team_id
from catchup.search.original.ids import OriginalDocumentRef
from catchup.search.original.schemas.slack import SlackMessageOriginalContentResponse
from catchup.search.original.schemas.slack import SlackMessageOriginalRawItem
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalFileUrlRequest
from catchup.server.search.schemas import OriginalFileUrlResponse


class SlackOriginalError(RuntimeError):
    """Raised when Slack original content cannot be fetched."""

    def __init__(self, message: str, *, status_code: int = 404) -> None:
        super().__init__(message)
        self.status_code = status_code


class SlackOriginalResolver:
    def __init__(
        self,
        *,
        bot_access_token: str | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
        session_factory: Callable[[], Session] | None = None,
        token_lookup: Callable[[Session, str], SlackOAuthToken | None] | None = None,
        workspace_lookup: Callable[[Session, str], SlackWorkspace | None] | None = None,
        channel_lookup: Callable[[Session, str], SlackChannel | None] | None = None,
        users_lookup: Callable[[Session, str, list[str]], dict[str, SlackUser]]
        | None = None,
        clock: Callable[[], datetime] | None = None,
        page_limit: int = 200,
    ) -> None:
        self._bot_access_token = bot_access_token
        self._client_factory = client_factory or SlackApiClientWrapper
        self._session_factory = session_factory or SessionLocal
        self._token_lookup = token_lookup or get_slack_token_by_team_id
        self._workspace_lookup = workspace_lookup or get_workspace
        self._channel_lookup = channel_lookup or get_channel
        self._users_lookup = users_lookup or get_users_by_ids
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._page_limit = page_limit

    async def resolve(
        self,
        *,
        request: OriginalContentRequest,
        ref: OriginalDocumentRef,
        db: Session | None = None,
    ) -> SlackMessageOriginalContentResponse:
        team_id = ref.identifiers["team_id"]
        channel_id = ref.identifiers["channel_id"]
        ts = ref.identifiers["ts"]
        bot_access_token = await self._get_bot_access_token(team_id=team_id, db=db)

        client = self._client_factory(bot_access_token, team_id)
        try:
            payload = await client.get_conversation_replies(
                channel=channel_id,
                ts=ts,
                cursor=request.next_cursor,
                limit=self._page_limit,
            )
        except SlackConnectorApiError as exc:
            raise SlackOriginalError(
                str(exc),
                status_code=_resolve_slack_error_status(exc),
            ) from exc
        metadata = await self._load_metadata(
            team_id=team_id,
            channel_id=channel_id,
            thread_ts=ts,
            user_ids=_collect_message_user_ids(payload),
            db=db,
        )

        return SlackMessageOriginalContentResponse(
            connector=SourceType.SLACK,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            title=_build_title(payload, fallback=ts),
            url=_build_permalink(
                workspace_domain=metadata.get("workspace_domain"),
                channel_id=channel_id,
                ts=ts,
            ),
            items=[
                SlackMessageOriginalRawItem(
                    id=ts,
                    raw_payload=payload,
                )
            ],
            metadata=metadata,
            next_cursor=_extract_next_cursor(payload),
            fetched_at=self._clock(),
        )

    async def resolve_file_url(
        self,
        *,
        request: OriginalFileUrlRequest,
        ref: OriginalDocumentRef,
        db: Session | None = None,
    ) -> OriginalFileUrlResponse:
        del request, ref, db
        raise SlackOriginalError("slack original file url is not supported", status_code=400)

    async def _get_bot_access_token(
        self,
        *,
        team_id: str,
        db: Session | None,
    ) -> str:
        if self._bot_access_token is not None:
            return self._bot_access_token

        token = await run_in_threadpool(
            self._get_bot_access_token_sync,
            team_id=team_id,
            db=db,
        )
        if token is None:
            raise SlackOriginalError("slack bot token not found")
        return token

    def _get_bot_access_token_sync(
        self,
        *,
        team_id: str,
        db: Session | None,
    ) -> str | None:
        if db is not None:
            token = self._token_lookup(db, team_id)
            return token.bot_access_token if token is not None else None

        with self._session_factory() as session:
            token = self._token_lookup(session, team_id)
            return token.bot_access_token if token is not None else None

    async def _load_metadata(
        self,
        *,
        team_id: str,
        channel_id: str,
        thread_ts: str,
        user_ids: list[str],
        db: Session | None,
    ) -> dict[str, Any]:
        return await run_in_threadpool(
            self._load_metadata_sync,
            team_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            user_ids=user_ids,
            db=db,
        )

    def _load_metadata_sync(
        self,
        *,
        team_id: str,
        channel_id: str,
        thread_ts: str,
        user_ids: list[str],
        db: Session | None,
    ) -> dict[str, Any]:
        if db is not None:
            return self._build_metadata(
                db=db,
                team_id=team_id,
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_ids=user_ids,
            )

        with self._session_factory() as session:
            return self._build_metadata(
                db=session,
                team_id=team_id,
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_ids=user_ids,
            )

    def _build_metadata(
        self,
        *,
        db: Session,
        team_id: str,
        channel_id: str,
        thread_ts: str,
        user_ids: list[str],
    ) -> dict[str, Any]:
        workspace = self._workspace_lookup(db, team_id)
        channel = self._channel_lookup(db, channel_id)
        users_by_id = self._users_lookup(db, team_id, user_ids)
        metadata: dict[str, Any] = {
            "team_id": team_id,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "users_by_id": {
                user_id: _map_user_metadata(user)
                for user_id, user in users_by_id.items()
            },
        }
        if channel is not None:
            metadata["channel_name"] = channel.name
        if workspace is not None:
            metadata["workspace_domain"] = workspace.domain
        return metadata


def _extract_next_cursor(payload: dict[str, Any]) -> str | None:
    response_metadata = payload.get("response_metadata")
    if not isinstance(response_metadata, dict):
        return None

    next_cursor = response_metadata.get("next_cursor")
    if isinstance(next_cursor, str) and next_cursor:
        return next_cursor
    return None


def _resolve_slack_error_status(exc: SlackConnectorApiError) -> int:
    if isinstance(exc, SlackRateLimitError):
        return 429

    error_code = exc.metadata.get("error")
    if error_code in {
        "invalid_arguments",
        "invalid_arg_name",
        "invalid_array_arg",
        "invalid_cursor",
        "invalid_form_data",
        "invalid_post_type",
        "invalid_ts_latest",
        "invalid_ts_oldest",
        "invalid_charset",
        "missing_post_type",
        "request_timeout",
    }:
        return 400
    if error_code in {
        "not_authed",
        "invalid_auth",
        "account_inactive",
        "token_expired",
        "token_revoked",
    }:
        return 401
    if error_code in {"channel_not_found", "thread_not_found", "message_not_found"}:
        return 404
    if error_code in {
        "not_in_channel",
        "missing_scope",
        "ekm_access_denied",
        "access_denied",
        "no_permission",
        "team_access_not_granted",
    }:
        return 403
    if exc.status_code is not None and 400 <= exc.status_code < 500:
        return exc.status_code
    if exc.status_code is not None and exc.status_code >= 500:
        return 502
    return 502


def _build_title(payload: dict[str, Any], *, fallback: str) -> str:
    messages = payload.get("messages")
    if isinstance(messages, list) and messages:
        parent = messages[0]
        if isinstance(parent, dict):
            text = parent.get("text")
            if isinstance(text, str) and text:
                return text
    return fallback


def _collect_message_user_ids(payload: dict[str, Any]) -> list[str]:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return []

    user_ids: set[str] = set()
    for message in messages:
        if not isinstance(message, dict):
            continue
        _add_string_value(user_ids, message.get("user"))
        _add_string_value(user_ids, message.get("parent_user_id"))
        _add_string_values(user_ids, message.get("reply_users"))
        reactions = message.get("reactions")
        if isinstance(reactions, list):
            for reaction in reactions:
                if isinstance(reaction, dict):
                    _add_string_values(user_ids, reaction.get("users"))
    return sorted(user_ids)


def _add_string_value(user_ids: set[str], value: Any) -> None:
    if isinstance(value, str) and value:
        user_ids.add(value)


def _add_string_values(user_ids: set[str], values: Any) -> None:
    if not isinstance(values, list):
        return
    for value in values:
        _add_string_value(user_ids, value)


def _map_user_metadata(user: SlackUser) -> dict[str, Any]:
    return {
        "id": user.user_id,
        "name": user.name,
        "display_name": user.display_name,
        "profile_image_url": user.avatar_url,
    }


def _build_permalink(
    *,
    workspace_domain: Any,
    channel_id: str,
    ts: str,
) -> str | None:
    if not isinstance(workspace_domain, str) or not workspace_domain:
        return None
    return f"https://{workspace_domain}.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"
