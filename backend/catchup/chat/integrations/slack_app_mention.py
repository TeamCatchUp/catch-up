from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from typing import Protocol

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.chat.factory import get_chat_service
from catchup.chat.schemas import ChatStreamingSourceResponse
from catchup.chat.schemas import ChatStreamingStatusResponse
from catchup.chat.schemas import ChatStreamingTokenResponse
from catchup.db.chat_room import get_chat_room
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.db.slack import bot_repository
from catchup.db.user_source_mapping import find_user_id_by_source_mapping
from catchup.db.users import get_user_with_full_context
from catchup.rag.schemas.context import GlobalCompanyContext
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.context import GlobalUserContext
from catchup.rag.schemas.context import GlobalWorkspaceContext

logger = structlog.get_logger(__name__)

MENTION_PATTERN = re.compile(r"<@[^>]+>")

EMPTY_QUERY_MESSAGE = "질문 내용을 함께 보내주세요."
UNMAPPED_USER_MESSAGE = "CatchUp에 등록되지 않은 사용자입니다."
THREAD_OWNER_MISMATCH_MESSAGE = (
    "이 스레드는 다른 사용자 세션에 연결되어 있어 현재는 이어서 질문할 수 없습니다."
)
MISSING_CONTEXT_MESSAGE = "CatchUp 사용자 컨텍스트를 찾지 못해 요청을 처리할 수 없습니다."
EMPTY_ANSWER_MESSAGE = "답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."
STREAM_FAILED_MESSAGE = "답변 생성 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."


@dataclass(slots=True, frozen=True)
class SlackAppMentionRequest:
    team_id: str
    channel_id: str
    thread_ts: str
    slack_user_id: str
    raw_text: str
    query: str


@dataclass(slots=True, frozen=True)
class SlackThreadSessionBinding:
    session_id: uuid.UUID
    user_id: int


class SlackAppMentionResponder(Protocol):
    async def on_node(self, node: str) -> None: ...

    async def append_answer_markdown(self, token: str) -> None: ...

    async def on_sources(self, sources: list[Any]) -> None: ...

    async def finish(self, *, answer: str, sources: list[Any]) -> None: ...

    async def fail(self, message: str) -> None: ...


ReplyPoster = Callable[[SlackAppMentionRequest, str], Awaitable[None]]
ResponderFactory = Callable[
    [SlackAppMentionRequest],
    Awaitable[SlackAppMentionResponder],
]


@lru_cache(maxsize=1)
def get_slack_app_mention_orchestrator() -> "SlackAppMentionOrchestrator":
    return SlackAppMentionOrchestrator()


class SlackAppMentionOrchestrator:
    async def handle_mention(
        self,
        mention: SlackAppMentionRequest,
        *,
        bot_user_id: str,
        post_thread_reply: ReplyPoster,
        responder_factory: ResponderFactory,
    ) -> None:
        if mention.slack_user_id == bot_user_id:
            logger.info(
                "slack_app_mention_ignored_self",
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
            )
            return

        if not mention.query:
            await post_thread_reply(mention, EMPTY_QUERY_MESSAGE)
            return

        user_id = await run_in_threadpool(
            self._find_internal_user_id_sync,
            mention.slack_user_id,
        )
        if user_id is None:
            await post_thread_reply(mention, UNMAPPED_USER_MESSAGE)
            return

        thread_session_binding = await run_in_threadpool(
            self._load_thread_session_binding_sync,
            mention,
        )
        if (
            thread_session_binding is not None
            and thread_session_binding.user_id != user_id
        ):
            await post_thread_reply(mention, THREAD_OWNER_MISMATCH_MESSAGE)
            return

        global_context = await run_in_threadpool(self._load_global_context_sync, user_id)
        if global_context is None:
            await post_thread_reply(mention, MISSING_CONTEXT_MESSAGE)
            return

        session_id = await run_in_threadpool(
            self._ensure_thread_binding_sync,
            mention,
            user_id,
        )

        responder = await responder_factory(mention)

        try:
            reply_text, sources = await self._run_chat_stream(
                global_context=global_context,
                session_id=session_id,
                query=mention.query,
                responder=responder,
            )
            await responder.finish(answer=reply_text, sources=sources)
        except Exception:
            await responder.fail(STREAM_FAILED_MESSAGE)
            raise

        await run_in_threadpool(
            self._attach_chat_room_if_ready_sync,
            mention,
            session_id,
            user_id,
        )

    async def _run_chat_stream(
        self,
        *,
        global_context: GlobalContext,
        session_id: uuid.UUID,
        query: str,
        responder: SlackAppMentionResponder,
    ) -> tuple[str, list[Any]]:
        answer_parts: list[str] = []
        sources: list[Any] = []
        chat_service = get_chat_service()
        markdown_enabled = False

        async for chunk in chat_service.chat_stream(
            global_context=global_context,
            session_id=session_id,
            query=query,
            tool_filters=[],
        ):
            if isinstance(chunk, ChatStreamingStatusResponse):
                await responder.on_node(chunk.node)
                if chunk.node in {"generate_final_answer", "chitchat"}:
                    markdown_enabled = True
                continue

            if isinstance(chunk, ChatStreamingTokenResponse):
                answer_parts.append(chunk.token)
                if markdown_enabled:
                    await responder.append_answer_markdown(chunk.token)
                continue

            if isinstance(chunk, ChatStreamingSourceResponse) and chunk.sources:
                sources = chunk.sources
                await responder.on_sources(sources)

        answer = "".join(answer_parts).strip() or EMPTY_ANSWER_MESSAGE
        return answer, sources

    def _find_internal_user_id_sync(self, slack_user_id: str) -> int | None:
        with SessionLocal() as db:
            return find_user_id_by_source_mapping(
                db,
                source_type=SourceType.SLACK,
                external_user_identifier=slack_user_id,
            )

    def _load_thread_session_binding_sync(
        self,
        mention: SlackAppMentionRequest,
    ) -> SlackThreadSessionBinding | None:
        with SessionLocal() as db:
            thread = bot_repository.get_slack_chat_thread(
                db,
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
            )
            if thread is None:
                return None
            return SlackThreadSessionBinding(
                session_id=thread.session_id,
                user_id=thread.user_id,
            )

    def _ensure_thread_binding_sync(
        self,
        mention: SlackAppMentionRequest,
        user_id: int,
    ) -> uuid.UUID:
        with SessionLocal() as db:
            thread = bot_repository.get_slack_chat_thread(
                db,
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
            )

            if thread is None:
                session_id = uuid.uuid4()
                bot_repository.create_slack_chat_thread(
                    db,
                    team_id=mention.team_id,
                    channel_id=mention.channel_id,
                    thread_ts=mention.thread_ts,
                    session_id=session_id,
                    user_id=user_id,
                    slack_user_id=mention.slack_user_id,
                    last_raw_text=mention.raw_text,
                )
                db.commit()
                return session_id

            bot_repository.touch_slack_chat_thread(
                thread,
                last_raw_text=mention.raw_text,
            )
            db.commit()
            return thread.session_id

    def _load_global_context_sync(self, user_id: int) -> GlobalContext | None:
        with SessionLocal() as db:
            db_user_full = get_user_with_full_context(db, user_id)
            if db_user_full is None or not db_user_full.workspace_links:
                return None

            target_workspace = db_user_full.workspace_links[0].workspace
            if target_workspace.company is None:
                return None

            return GlobalContext(
                user=GlobalUserContext.model_validate(db_user_full),
                workspace=GlobalWorkspaceContext.model_validate(target_workspace),
                company=GlobalCompanyContext.model_validate(target_workspace.company),
            )

    def _attach_chat_room_if_ready_sync(
        self,
        mention: SlackAppMentionRequest,
        session_id: uuid.UUID,
        user_id: int,
    ) -> None:
        with SessionLocal() as db:
            room = get_chat_room(
                db=db,
                session_id=session_id,
                user_id=user_id,
            )
            if room is None:
                return

            thread = bot_repository.get_slack_chat_thread(
                db,
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
            )
            if thread is None or thread.chat_room_id == room.id:
                return

            bot_repository.attach_chat_room(thread, chat_room_id=room.id)
            db.commit()


def parse_app_mention_event(
    team_id: str,
    event: dict[str, Any],
) -> SlackAppMentionRequest | None:
    channel_id = str(event.get("channel") or "").strip()
    slack_user_id = str(event.get("user") or "").strip()
    raw_text = str(event.get("text") or "")
    event_ts = str(event.get("ts") or "").strip()
    thread_ts = str(event.get("thread_ts") or event_ts).strip()

    if not team_id or not channel_id or not slack_user_id or not event_ts:
        return None

    return SlackAppMentionRequest(
        team_id=team_id,
        channel_id=channel_id,
        thread_ts=thread_ts,
        slack_user_id=slack_user_id,
        raw_text=raw_text,
        query=extract_app_mention_query(raw_text),
    )


def extract_app_mention_query(text: str) -> str:
    without_mentions = MENTION_PATTERN.sub(" ", text or "")
    normalized = " ".join(without_mentions.split())
    return normalized.strip()
