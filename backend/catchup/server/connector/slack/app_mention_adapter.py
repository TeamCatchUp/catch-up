import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.chat.integrations.slack_app_mention import BUSY_NOTICE_BODY
from catchup.chat.integrations.slack_app_mention import BUSY_NOTICE_TITLE
from catchup.chat.integrations.slack_app_mention import SlackAppMentionRequest
from catchup.chat.integrations.slack_app_mention import SlackAppMentionResponder
from catchup.chat.integrations.slack_app_mention import extract_mentioned_slack_user_ids
from catchup.chat.integrations.slack_app_mention import (
    get_slack_app_mention_orchestrator,
)
from catchup.chat.integrations.slack_app_mention import parse_app_mention_event
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.db.slack.oauth_repository import get_slack_token_by_team_id
from catchup.db.user_source_mapping import find_user_names_by_source_mappings
from catchup.server.connector.slack.plan_stream import SlackPlanResponder
from catchup.server.connector.slack.schemas import SlackWebhookRequest

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class SlackTeamBotAuth:
    bot_access_token: str
    bot_user_id: str


class SlackAppMentionClientTransport:
    def __init__(self, client: SlackApiClientWrapper) -> None:
        self.client = client

    async def post_thread_reply(
        self,
        mention: SlackAppMentionRequest,
        text: str,
    ) -> None:
        await self.client.post_message(
            channel=mention.channel_id,
            thread_ts=mention.thread_ts,
            text=text,
        )

    async def post_busy_notice(
        self,
        mention: SlackAppMentionRequest,
    ) -> None:
        await self.client.post_ephemeral(
            channel=mention.channel_id,
            user=mention.slack_user_id,
            thread_ts=mention.thread_ts,
            text=BUSY_NOTICE_BODY,
            blocks=self._build_busy_notice_blocks(),
        )

    async def start_responder(
        self,
        mention: SlackAppMentionRequest,
    ) -> SlackAppMentionResponder:
        return await SlackPlanResponder.start(
            client=self.client,
            channel_id=mention.channel_id,
            thread_ts=mention.thread_ts,
            team_id=mention.team_id,
            user_id=mention.slack_user_id,
            query=mention.query,
        )

    def _build_busy_notice_blocks(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "section",
                "block_id": "catchup_app_mention_busy_title_v1",
                "text": {
                    "type": "mrkdwn",
                    "text": BUSY_NOTICE_TITLE,
                },
            },
            {
                "type": "section",
                "block_id": "catchup_app_mention_busy_body_v1",
                "text": {
                    "type": "mrkdwn",
                    "text": BUSY_NOTICE_BODY,
                },
            },
            {"type": "divider"},
        ]


def schedule_app_mention(request: SlackWebhookRequest) -> None:
    task = asyncio.create_task(get_slack_app_mention_adapter().handle(request))
    task.add_done_callback(_log_background_failure)


def _log_background_failure(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except Exception:
        logger.exception("slack_app_mention_failed")


@lru_cache(maxsize=1)
def get_slack_app_mention_adapter() -> "SlackAppMentionAdapter":
    return SlackAppMentionAdapter()


class SlackAppMentionAdapter:
    async def handle(self, request: SlackWebhookRequest) -> None:
        team_bot_auth = await run_in_threadpool(
            self._load_team_auth_sync,
            request.team_id,
        )
        if team_bot_auth is None:
            logger.warning(
                "slack_app_mention_missing_team_token",
                team_id=request.team_id,
            )
            return

        mentioned_user_names_by_id = await run_in_threadpool(
            self._load_mentioned_user_names_sync,
            str(request.event.get("text") or ""),
            team_bot_auth.bot_user_id,
        )
        mention = parse_app_mention_event(
            request.team_id,
            request.event,
            bot_user_id=team_bot_auth.bot_user_id,
            mentioned_user_names_by_id=mentioned_user_names_by_id,
        )
        if mention is None:
            logger.info(
                "slack_app_mention_ignored_invalid_payload",
                team_id=request.team_id,
            )
            return

        client = SlackApiClientWrapper(team_bot_auth.bot_access_token, mention.team_id)
        transport = SlackAppMentionClientTransport(client)
        await get_slack_app_mention_orchestrator().handle_mention(
            mention,
            bot_user_id=team_bot_auth.bot_user_id,
            transport=transport,
        )

    def _load_team_auth_sync(self, team_id: str) -> SlackTeamBotAuth | None:
        with SessionLocal() as db:
            token = get_slack_token_by_team_id(db, team_id)
            if token is None:
                return None
            return SlackTeamBotAuth(
                bot_access_token=token.bot_access_token,
                bot_user_id=token.bot_user_id,
            )

    def _load_mentioned_user_names_sync(
        self,
        raw_text: str,
        bot_user_id: str,
    ) -> dict[str, str]:
        mentioned_user_ids = [
            mentioned_user_id
            for mentioned_user_id in extract_mentioned_slack_user_ids(raw_text)
            if mentioned_user_id != bot_user_id
        ]
        if not mentioned_user_ids:
            return {}

        with SessionLocal() as db:
            return find_user_names_by_source_mappings(
                db,
                source_type=SourceType.SLACK,
                external_user_identifiers=mentioned_user_ids,
            )
