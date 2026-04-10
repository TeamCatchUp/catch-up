import asyncio
from dataclasses import dataclass
from functools import lru_cache

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.chat.integrations.slack_app_mention import SlackAppMentionRequest
from catchup.chat.integrations.slack_app_mention import (
    get_slack_app_mention_orchestrator,
)
from catchup.chat.integrations.slack_app_mention import parse_app_mention_event
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.db.engine import SessionLocal
from catchup.db.slack.oauth_repository import get_slack_token_by_team_id
from catchup.server.connector.slack.plan_stream import SlackPlanResponder
from catchup.server.connector.slack.schemas import SlackWebhookRequest

logger = structlog.get_logger(__name__)

@dataclass(slots=True, frozen=True)
class SlackTeamBotAuth:
    bot_access_token: str
    bot_user_id: str


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
        mention = parse_app_mention_event(request.team_id, request.event)
        if mention is None:
            logger.info(
                "slack_app_mention_ignored_invalid_payload",
                team_id=request.team_id,
            )
            return

        team_bot_auth = await run_in_threadpool(
            self._load_team_auth_sync,
            mention.team_id,
        )
        if team_bot_auth is None:
            logger.warning(
                "slack_app_mention_missing_team_token",
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
            )
            return

        client = SlackApiClientWrapper(team_bot_auth.bot_access_token, mention.team_id)
        await get_slack_app_mention_orchestrator().handle_mention(
            mention,
            bot_user_id=team_bot_auth.bot_user_id,
            post_thread_reply=lambda mention_request, text: self._post_thread_reply(
                client,
                mention_request,
                text,
            ),
            responder_factory=lambda mention_request: self._start_responder(
                client,
                mention_request,
            ),
        )

    async def _post_thread_reply(
        self,
        client: SlackApiClientWrapper,
        mention: SlackAppMentionRequest,
        text: str,
    ) -> None:
        await client.post_message(
            channel=mention.channel_id,
            thread_ts=mention.thread_ts,
            text=text,
        )

    async def _start_responder(
        self,
        client: SlackApiClientWrapper,
        mention: SlackAppMentionRequest,
    ) -> SlackPlanResponder:
        return await SlackPlanResponder.start(
            client=client,
            channel_id=mention.channel_id,
            thread_ts=mention.thread_ts,
            team_id=mention.team_id,
            user_id=mention.slack_user_id,
            query=mention.query,
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
