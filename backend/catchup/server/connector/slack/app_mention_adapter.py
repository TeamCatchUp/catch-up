import asyncio
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from functools import lru_cache
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.chat.integrations.slack_app_mention import BUSY_NOTICE_BODY
from catchup.chat.integrations.slack_app_mention import BUSY_NOTICE_TITLE
from catchup.chat.integrations.slack_app_mention import SlackAppMentionRequest
from catchup.chat.integrations.slack_app_mention import SlackAppMentionResponder
from catchup.chat.integrations.slack_app_mention import extract_app_mention_query
from catchup.chat.integrations.slack_app_mention import extract_mentioned_slack_user_ids
from catchup.chat.integrations.slack_app_mention import (
    get_slack_app_mention_orchestrator,
)
from catchup.chat.integrations.slack_app_mention import parse_app_mention_event
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.transformers import SlackTransformer
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.db.slack.oauth_repository import get_slack_token_by_team_id
from catchup.db.user_source_mapping import find_user_names_by_source_mappings
from catchup.server.connector.slack.feedback_actions import resolve_frontend_base_url
from catchup.server.connector.slack.plan_stream import SlackPlanResponder
from catchup.server.connector.slack.schemas import SlackWebhookRequest

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class SlackTeamBotAuth:
    bot_access_token: str
    bot_user_id: str


@dataclass(slots=True, frozen=True)
class SlackThreadContextMessage:
    ts: str
    user_id: str
    text: str


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

    async def post_signup_prompt(
        self,
        mention: SlackAppMentionRequest,
        text: str,
    ) -> None:
        await self.client.post_message(
            channel=mention.channel_id,
            thread_ts=mention.thread_ts,
            text=text,
            blocks=self._build_signup_prompt_blocks(text),
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

    def _build_signup_prompt_blocks(self, text: str) -> list[dict[str, Any]]:
        return [
            {
                "type": "section",
                "block_id": "catchup_app_mention_signup_message_v1",
                "text": {
                    "type": "mrkdwn",
                    "text": text,
                },
            },
            {
                "type": "actions",
                "block_id": "catchup_app_mention_signup_actions_v1",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "catchup_signup_redirect_v1",
                        "text": {
                            "type": "plain_text",
                            "text": "CatchUp 회원가입",
                            "emoji": False,
                        },
                        "url": resolve_frontend_base_url(),
                    }
                ],
            },
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

        raw_text = str(request.event.get("text") or "")
        mentioned_user_names_by_id = await run_in_threadpool(
            self._load_user_names_sync,
            self._extract_non_bot_mentioned_user_ids(
                raw_text=raw_text,
                bot_user_id=team_bot_auth.bot_user_id,
            ),
        )
        mention = self._parse_mention(
            request=request,
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
        additional_context = await self._build_additional_context(
            client=client,
            mention=mention,
            bot_user_id=team_bot_auth.bot_user_id,
        )
        await get_slack_app_mention_orchestrator().handle_mention(
            mention,
            bot_user_id=team_bot_auth.bot_user_id,
            transport=transport,
            additional_context=additional_context,
        )

    def _parse_mention(
        self,
        *,
        request: SlackWebhookRequest,
        bot_user_id: str,
        mentioned_user_names_by_id: dict[str, str],
    ) -> SlackAppMentionRequest | None:
        return parse_app_mention_event(
            request.team_id,
            request.event,
            bot_user_id=bot_user_id,
            mentioned_user_names_by_id=mentioned_user_names_by_id,
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

    def _extract_non_bot_mentioned_user_ids(
        self,
        raw_text: str,
        bot_user_id: str,
    ) -> list[str]:
        return [
            mentioned_user_id
            for mentioned_user_id in extract_mentioned_slack_user_ids(raw_text)
            if mentioned_user_id != bot_user_id
        ]

    async def _build_additional_context(
        self,
        *,
        client: SlackApiClientWrapper,
        mention: SlackAppMentionRequest,
        bot_user_id: str,
    ) -> str | None:
        if mention.thread_ts == mention.event_ts:
            return None

        try:
            thread_messages = await self._load_thread_messages_before_current_question(
                client=client,
                mention=mention,
            )
        except Exception:
            logger.exception(
                "slack_app_mention_thread_context_load_failed",
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
                event_ts=mention.event_ts,
            )
            return None

        context_messages = self._extract_context_messages(
            thread_messages,
            bot_user_id=bot_user_id,
        )
        if not context_messages:
            return None

        context_user_ids = self._collect_context_user_ids(context_messages)
        user_names_by_id = await run_in_threadpool(
            self._load_user_names_sync,
            context_user_ids,
        )
        return self._format_additional_context(
            context_messages,
            user_names_by_id=user_names_by_id,
        )

    async def _load_thread_messages_before_current_question(
        self,
        *,
        client: SlackApiClientWrapper,
        mention: SlackAppMentionRequest,
    ) -> list[dict[str, Any]]:
        response = await client.get_conversation_replies(
            channel=mention.channel_id,
            ts=mention.thread_ts,
            latest=mention.event_ts,
            inclusive=False,
        )
        return list(response.get("messages") or [])

    def _extract_context_messages(
        self,
        thread_messages: list[dict[str, Any]],
        *,
        bot_user_id: str,
    ) -> list[SlackThreadContextMessage]:
        visible_messages = [
            SlackThreadContextMessage(
                ts=str(message.get("ts") or "").strip(),
                user_id=str(message.get("user") or "").strip(),
                text=str(message.get("text") or "").strip(),
            )
            for message in thread_messages
            if self._should_include_context_message(message, bot_user_id=bot_user_id)
        ]

        last_question_index = self._find_last_question_index(
            visible_messages,
            bot_user_id=bot_user_id,
        )
        if last_question_index < 0:
            return visible_messages
        return visible_messages[last_question_index + 1:]

    def _should_include_context_message(
        self,
        message: dict[str, Any],
        *,
        bot_user_id: str,
    ) -> bool:
        text = str(message.get("text") or "").strip()
        user_id = str(message.get("user") or "").strip()

        if not text or not user_id:
            return False

        if user_id == bot_user_id:
            return False

        if message.get("bot_id") or message.get("subtype") == "bot_message":
            return False

        return True

    def _find_last_question_index(
        self,
        context_messages: list[SlackThreadContextMessage],
        *,
        bot_user_id: str,
    ) -> int:
        for index in range(len(context_messages) - 1, -1, -1):
            if self._is_question_boundary_message(
                context_messages[index],
                bot_user_id=bot_user_id,
            ):
                return index
        return -1

    def _is_question_boundary_message(
        self,
        message: SlackThreadContextMessage,
        *,
        bot_user_id: str,
    ) -> bool:
        normalized_text = " ".join((message.text or "").split())
        if not normalized_text:
            return False

        extracted_query = extract_app_mention_query(
            normalized_text,
            bot_user_id=bot_user_id,
        )
        return bool(extracted_query) and extracted_query != normalized_text

    def _collect_context_user_ids(
        self,
        context_messages: list[SlackThreadContextMessage],
    ) -> list[str]:
        user_ids: list[str] = []
        seen_user_ids: set[str] = set()

        for message in context_messages:
            for user_id in (message.user_id, *extract_mentioned_slack_user_ids(message.text)):
                resolved_user_id = str(user_id or "").strip()
                if not resolved_user_id or resolved_user_id in seen_user_ids:
                    continue
                seen_user_ids.add(resolved_user_id)
                user_ids.append(resolved_user_id)

        return user_ids

    def _load_user_names_sync(
        self,
        slack_user_ids: list[str],
    ) -> dict[str, str]:
        if not slack_user_ids:
            return {}

        with SessionLocal() as db:
            return find_user_names_by_source_mappings(
                db,
                source_type=SourceType.SLACK,
                external_user_identifiers=slack_user_ids,
            )

    def _format_additional_context(
        self,
        context_messages: list[SlackThreadContextMessage],
        *,
        user_names_by_id: dict[str, str],
    ) -> str | None:
        transformer = SlackTransformer.from_user_names(user_names_by_id)
        lines = ["Thread context:"]

        for message in context_messages:
            normalized_text = transformer.normalize_text_for_llm(message.text).strip()
            if not normalized_text:
                continue

            author_name = user_names_by_id.get(message.user_id) or message.user_id
            message_time = self._format_message_time(message.ts)
            lines.append(f"- [{author_name} at {message_time}] {normalized_text}")

        if len(lines) == 1:
            return None
        return "\n".join(lines)

    def _format_message_time(self, ts: str) -> str:
        try:
            message_time = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (TypeError, ValueError):
            return ts
        return message_time.strftime("%Y-%m-%d %H:%M")
