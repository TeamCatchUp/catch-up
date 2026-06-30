"""
Slack app_mention 채팅 orchestration.

webhook_api -> sync.ingress.slack -> app_mention_adapter
-> SlackAppMentionOrchestrator -> chat_service.chat_stream
-> SlackPlanResponder / SlackApiClientWrapper -> interaction_handler.

이 모듈은 Slack bot 채팅 흐름에서 비즈니스 규칙 중심을 맡는다.
Slack transport 세부사항은 adapter / responder 경계에 남겨 두고,
채팅 완료 후 필요한 참조 정보만 responder에 전달
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from typing import Protocol

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.chat.factory import get_chat_service
from catchup.chat.schemas import ChatStreamingProcessResponse
from catchup.chat.schemas import ChatStreamingSourceResponse
from catchup.chat.schemas import ChatStreamingTokenResponse
from catchup.db.chat_room import get_chat_room_by_session_id
from catchup.db.chat_room import get_latest_assistant_message
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.db.slack import bot_repository
from catchup.db.user_prompt_settings import get_user_prompt_settings
from catchup.db.user_source_mapping import find_user_id_by_source_mapping
from catchup.db.users import get_user_with_full_context
from catchup.schemas.context import GlobalCompanyContext
from catchup.schemas.context import GlobalContext
from catchup.schemas.context import GlobalUserContext
from catchup.schemas.context import GlobalWorkspaceContext
from catchup.schemas.prompt_settings import PromptSettings

logger = structlog.get_logger(__name__)

SLACK_USER_MENTION_PATTERN = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]+)?>")

EMPTY_QUERY_MESSAGE = "질문이 비어있어요 🥲 \n 어떤게 궁금하신가요 ?"
UNMAPPED_USER_MESSAGE = "CatchUp에서 사용자 정보를 찾을 수 없어요 🥲"
MISSING_CONTEXT_MESSAGE = "CatchUp에서 사용자 정보를 찾을 수 없어요 🥲"
EMPTY_ANSWER_MESSAGE = "죄송합니다 🥲 답변 생성중에 문제가 발생했어요\n잠시 후 다시 시도해 주세요"
STREAM_FAILED_MESSAGE = "죄송합니다 🥲 답변 생성중에 문제가 발생했어요\n잠시 후 다시 시도해 주세요"
BUSY_NOTICE_TITLE = "🥲 이전 답변이 아직 생성중이에요"
BUSY_NOTICE_BODY = (
    "답변 생성이 완료되면 다시 질문 부탁드려요 🙇"
)
APP_MENTION_CHAT_MODE = "fast"


@dataclass(slots=True, frozen=True)
class SlackAppMentionRequest:
    team_id: str
    channel_id: str
    thread_ts: str
    event_ts: str
    slack_user_id: str
    raw_text: str
    query: str


@dataclass(slots=True, frozen=True)
class SlackChatAnswerRef:
    session_id: uuid.UUID
    assistant_message_id: int | None = None


class SlackAppMentionResponder(Protocol):
    async def on_process(self, process: ChatStreamingProcessResponse) -> None: ...

    async def append_answer_markdown(self, token: str) -> None: ...

    async def on_sources(self, sources: list[Any]) -> None: ...

    async def finish(
        self,
        *,
        answer: str,
        sources: list[Any],
        answer_ref: SlackChatAnswerRef | None = None,
    ) -> None: ...

    async def fail(self, message: str) -> None: ...


class SlackAppMentionTransport(Protocol):
    async def post_thread_reply(self, mention: SlackAppMentionRequest, text: str) -> None: ...

    async def post_signup_prompt(self, mention: SlackAppMentionRequest, text: str) -> None: ...

    async def post_busy_notice(self, mention: SlackAppMentionRequest) -> None: ...

    async def start_responder(self, mention: SlackAppMentionRequest) -> SlackAppMentionResponder: ...


@lru_cache(maxsize=1)
def get_slack_app_mention_orchestrator() -> "SlackAppMentionOrchestrator":
    return SlackAppMentionOrchestrator()


class SlackAppMentionOrchestrator:
    async def handle_mention(
        self,
        mention: SlackAppMentionRequest,
        *,
        bot_user_id: str,
        transport: SlackAppMentionTransport,
        additional_context: str | None = None,
    ) -> None:
        # 봇 자신의 멘션은 무시
        if mention.slack_user_id == bot_user_id:
            logger.info(
                "slack_app_mention_ignored_self",
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
            )
            return

        if not mention.query:
            await transport.post_thread_reply(mention, EMPTY_QUERY_MESSAGE)
            return

        # Slack User -> CatchUp User
        user_id = await run_in_threadpool(
            self._find_internal_user_id_sync,
            mention.slack_user_id,
        )
        if user_id is None:
            await transport.post_signup_prompt(mention, UNMAPPED_USER_MESSAGE)
            return

        # Global Context Loading
        global_context = await run_in_threadpool(self._load_global_context_sync, user_id)
        if global_context is None:
            await transport.post_signup_prompt(mention, MISSING_CONTEXT_MESSAGE)
            return

        # 스레드 실행 권한을 확보하고 현재 처리 가능 상태인지 확인한다.
        # Thread(Session) lease를 확인 및 획득
        acquire_result = await run_in_threadpool(
            self._acquire_thread_session_sync,
            mention,
            user_id,
        )
        # 이전 답변이 생성 중
        if acquire_result.outcome == "busy":
            await transport.post_busy_notice(mention)
            return
        if acquire_result.session_id is None or acquire_result.lease_started_at is None:
            raise RuntimeError("slack app mention thread acquisition returned no lease")
        if acquire_result.reclaimed_stale:
            logger.info(
                "slack_app_mention_reclaimed_stale_lease",
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
                session_id=str(acquire_result.session_id),
            )

        session_id = acquire_result.session_id
        lease_started_at = acquire_result.lease_started_at

        try:
            # User Prompt Settings Loading
            prompt_settings = await run_in_threadpool(
                self._load_prompt_settings_sync,
                user_id,
            )
            responder = await transport.start_responder(mention)

            try:
                reply_text, sources = await self._run_chat_stream(
                    global_context=global_context,
                    prompt_settings=prompt_settings,
                    session_id=session_id,
                    query=mention.query,
                    additional_context=additional_context,
                    responder=responder,
                )
                answer_ref = await run_in_threadpool(
                    self._load_answer_ref_sync,
                    session_id,
                )
                await responder.finish(
                    answer=reply_text,
                    sources=sources,
                    answer_ref=answer_ref,
                )
            except Exception:
                await responder.fail(STREAM_FAILED_MESSAGE)
                raise

            # 답변이 종료된 이후에 Session을 Chat Room에 연결
            await run_in_threadpool(
                self._attach_chat_room_if_ready_sync,
                mention,
                session_id,
            )
        finally:
            # 처리 종료 이후에 lease 해제
            released = await run_in_threadpool(
                self._release_thread_execution_sync,
                mention,
                lease_started_at,
            )
            if not released:
                logger.warning(
                    "slack_app_mention_release_missed",
                    team_id=mention.team_id,
                    channel_id=mention.channel_id,
                    thread_ts=mention.thread_ts,
                    session_id=str(session_id),
                )

    async def _run_chat_stream(
        self,
        *,
        global_context: GlobalContext,
        prompt_settings: PromptSettings,
        session_id: uuid.UUID,
        query: str,
        additional_context: str | None,
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
            additional_context=additional_context,
            prompt_settings=prompt_settings,
            mode=APP_MENTION_CHAT_MODE,
            is_slack=True,
        ):
            if isinstance(chunk, ChatStreamingProcessResponse):
                await responder.on_process(chunk)
                if chunk.node in {"generate_final_answer_fast", "generate_final_answer", "direct_answer"}:
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

    def _acquire_thread_session_sync(
        self,
        mention: SlackAppMentionRequest,
        user_id: int,
    ) -> bot_repository.SlackThreadAcquireResult:
        with SessionLocal() as db:
            result = bot_repository.acquire_or_reject_slack_thread(
                db=db,
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
                user_id=user_id,
                slack_user_id=mention.slack_user_id,
                last_raw_text=mention.raw_text,
            )
            if result.outcome == "acquired":
                db.commit()
            else:
                db.rollback()
            return result

    def _release_thread_execution_sync(
        self,
        mention: SlackAppMentionRequest,
        lease_started_at: Any,
    ) -> bool:
        with SessionLocal() as db:
            released = bot_repository.release_slack_chat_thread(
                db=db,
                team_id=mention.team_id,
                channel_id=mention.channel_id,
                thread_ts=mention.thread_ts,
                lease_started_at=lease_started_at,
            )
            db.commit()
            return released

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

    def _load_prompt_settings_sync(self, user_id: int) -> PromptSettings:
        with SessionLocal() as db:
            settings = get_user_prompt_settings(db=db, user_id=user_id)
            if settings is None:
                return PromptSettings(platform="slack")

            return PromptSettings.model_validate(settings).model_copy(
                update={"platform": "slack"},
            )

    def _attach_chat_room_if_ready_sync(
        self,
        mention: SlackAppMentionRequest,
        session_id: uuid.UUID,
    ) -> None:
        with SessionLocal() as db:
            room = get_chat_room_by_session_id(db=db, session_id=session_id)
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

    def _load_answer_ref_sync(
        self,
        session_id: uuid.UUID,
    ) -> SlackChatAnswerRef | None:
        with SessionLocal() as db:
            # 저장된 room/assistant 메시지를 기준으로 Slack 버튼 URL을 확정
            # Slack 서버 발급 session_id 환경에서는 user_id 검증 없이 조회 (multi-user 지원)
            room = get_chat_room_by_session_id(
                db=db,
                session_id=session_id,
            )
            if room is None:
                return None

            assistant_message = get_latest_assistant_message(db, room.id)
            if assistant_message is None:
                return SlackChatAnswerRef(session_id=session_id)

            return SlackChatAnswerRef(
                session_id=session_id,
                assistant_message_id=assistant_message.id,
            )


def parse_app_mention_event(
    team_id: str,
    event: dict[str, Any],
    *,
    bot_user_id: str,
    mentioned_user_names_by_id: Mapping[str, str] | None = None,
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
        event_ts=event_ts,
        slack_user_id=slack_user_id,
        raw_text=raw_text,
        query=extract_app_mention_query(
            raw_text,
            bot_user_id=bot_user_id,
            mentioned_user_names_by_id=mentioned_user_names_by_id,
        ),
    )


def extract_mentioned_slack_user_ids(text: str) -> list[str]:
    mentioned_user_ids: list[str] = []
    seen_user_ids: set[str] = set()

    for mentioned_user_id in SLACK_USER_MENTION_PATTERN.findall(text or ""):
        if mentioned_user_id in seen_user_ids:
            continue
        seen_user_ids.add(mentioned_user_id)
        mentioned_user_ids.append(mentioned_user_id)

    return mentioned_user_ids


def extract_app_mention_query(
    text: str,
    *,
    bot_user_id: str,
    mentioned_user_names_by_id: Mapping[str, str] | None = None,
) -> str:
    user_names_by_id = mentioned_user_names_by_id or {}

    def replace_mention(match: re.Match[str]) -> str:
        mentioned_user_id = match.group(1)
        if mentioned_user_id == bot_user_id:
            return " "

        resolved_name = user_names_by_id.get(mentioned_user_id)
        if resolved_name:
            return resolved_name

        return match.group(0)

    normalized = " ".join(SLACK_USER_MENTION_PATTERN.sub(replace_mention, text or "").split())
    return normalized.strip()
