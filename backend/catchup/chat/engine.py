import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Literal

import structlog
from fastapi.concurrency import run_in_threadpool
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langgraph.types import StateSnapshot

from catchup.audit.actions import ChatAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import ChatAuditMetadata
from catchup.chat.chat_room import generate_chat_room_title
from catchup.chat.event_store import ChatEventStore
from catchup.chat.schemas import ChatResponse
from catchup.chat.schemas import StreamEvent
from catchup.chat.stream_processor import ChatStreamProcessor
from catchup.chat.utils import restore_conversation_context
from catchup.configs.config import settings
from catchup.costs.contexts.chat import ChatTokenUsageContext
from catchup.costs.emitters import emit_chat_token_usage_event
from catchup.db.chat_room import add_message
from catchup.db.chat_room import create_chat_room
from catchup.db.chat_room import get_chat_room
from catchup.db.chat_room import get_chat_room_by_session_id
from catchup.db.chat_room import soft_delete_last_conversation_turn
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.langgraph.checkpoint import get_langgraph_checkpointer
from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.langfuse.configs import get_observe
from catchup.rag.graph import get_compiled_graph
from catchup.schemas.context import GlobalContext
from catchup.schemas.prompt_settings import PromptSettings

logger = structlog.get_logger()

# Langfuse
observe = get_observe()

_MODE_CEILING: dict[str, str] = {
    "fast": "standard",
    "standard": "complex",
}


@dataclass(frozen=True, slots=True)
class RunProfile:
    """Slack 통합과 run_background()가 공유하는 run()의 취소/에러 복구 차이를 데이터로 표현한다."""

    save_partial: bool
    reraise_on_cancel: bool
    cancelled_log_event: str
    cancelled_audit_context: str
    error_log_event: str
    error_audit_context: str
    finished_log_event: str


SLACK_RUN_PROFILE = RunProfile(
    save_partial=False,
    reraise_on_cancel=True,
    cancelled_log_event="stream_cancelled",
    cancelled_audit_context="connection_cancelled",
    error_log_event="streaming_error",
    error_audit_context="streaming_error",
    finished_log_event="streaming_finished",
)

BACKGROUND_RUN_PROFILE = RunProfile(
    save_partial=True,
    reraise_on_cancel=False,
    cancelled_log_event="background_task_cancelled",
    cancelled_audit_context="background_task_cancelled",
    error_log_event="background_streaming_error",
    error_audit_context="background_streaming_error",
    finished_log_event="background_task_finished",
)


class ChatService:
    def __init__(self):
        self._app = None

        if settings.ENABLE_LANGFUSE:
            logger.info(
                "langfuse_initialized", host=settings.LANGFUSE_BASE_URL, active=True
            )

    def _get_app(self):
        if self._app is None:
            checkpointer = get_langgraph_checkpointer()
            self._app = get_compiled_graph(checkpointer)
        return self._app

    async def run(
        self,
        global_context: GlobalContext,
        prompt_settings: PromptSettings,
        session_id: uuid.UUID,
        sink: Callable[[StreamEvent], Awaitable[None]],
        *,
        profile: RunProfile,
        tool_filters: list[SourceType] | None = None,
        query: str | None = None,
        additional_context: str | None = None,
        mode: Literal["fast", "standard"] = "standard",
        is_slack: bool = False,
    ) -> None:
        """LangGraph를 실행하고 이벤트를 sink로 전달한다.

        Slack 통합(SLACK_RUN_PROFILE)과 run_background()(BACKGROUND_RUN_PROFILE)가
        공유하는 실행 로직으로, 두 경로의 취소/에러 복구 차이는 profile로 표현한다.
        """
        start = time.perf_counter()
        ChatTokenUsageContext.init()

        base_config = None
        processor = None
        saved_message_id: int | None = None
        trace_id: str | None = None
        room_id: int | None = None

        try:
            room_id = await self._ensure_chat_room(
                global_context, session_id, query, is_slack=is_slack
            )

            app = self._get_app()
            base_config, invoke_config, trace_id = self._setup_config(session_id)
            lg_current_state = await app.aget_state(base_config)

            input_messages = await run_in_threadpool(
                self._resolve_input_messages,
                session_id,
                query,
                lg_current_state,
                additional_context,
            )

            saved_message_id = await self._save_message_content(
                room_id,
                "user",
                query,
                user_id=global_context.user.id,
            )

            inputs = {
                "messages": input_messages,
                "original_query": query,
                "global_context": global_context,
                "tool_filters": tool_filters,
                "prompt_settings": prompt_settings,
                "max_pipeline_type": _MODE_CEILING.get(mode, "complex"),
                "vector_search_queries": [],
                "agent_iteration": 0,
                "accumulated_docs": [],
                "agent_seen_doc_ids": [],
                "confirmed_essential_doc_ids": [],
                "agent_stop_reason": None,
                "token_breakdown": {},
                "rerank_count": 0,
                "slack_thread_context": additional_context,
            }

            processor = ChatStreamProcessor(
                session_id=session_id,
                room_id=room_id,
                save_message=self._save_message_content,
                langfuse_trace_id=trace_id,
            )

            async for event in app.astream_events(inputs, invoke_config, version="v2"):
                async for parsed_event in processor.process(event):
                    await sink(parsed_event)

        except asyncio.CancelledError:
            elapsed = time.perf_counter() - start
            logger.warning(
                profile.cancelled_log_event,
                session_id=str(session_id),
                elapsed_seconds=round(elapsed, 2),
                cancelled_at_node=processor.context.current_node
                if processor is not None
                else None,
            )
            if profile.save_partial and room_id is not None:
                try:
                    await self._save_partial_if_any(processor, room_id, trace_id)
                except Exception:
                    logger.exception(
                        "partial_save_failed_on_cancel",
                        session_id=str(session_id),
                    )
            emit_audit_event(
                action=ChatAction.GENERATE_RESPONSE,
                status=AuditStatus.FAILURE,
                level=AuditLevel.WARNING,
                metadata=ChatAuditMetadata(
                    context=profile.cancelled_audit_context,
                    session_id=session_id,
                ),
            )
            if profile.reraise_on_cancel:
                raise

        except Exception:
            logger.exception(profile.error_log_event)

            if saved_message_id is not None and room_id is not None:
                saved_partial = False
                if profile.save_partial:
                    saved_partial = bool(
                        processor is not None
                        and processor.context.accumulated_content.strip()
                    )
                    if saved_partial:
                        await self._save_partial_if_any(processor, room_id, trace_id)
                if not saved_partial:
                    await self.reset_last_turn(room_id=room_id, session_id=session_id)

            emit_audit_event(
                action=ChatAction.GENERATE_RESPONSE,
                status=AuditStatus.FAILURE,
                level=AuditLevel.ERROR,
                metadata=ChatAuditMetadata(
                    session_id=session_id,
                    context=profile.error_audit_context,
                ),
            )

        else:
            emit_audit_event(
                action=ChatAction.GENERATE_RESPONSE,
                status=AuditStatus.SUCCESS,
                level=AuditLevel.INFO,
                metadata=ChatAuditMetadata(session_id=session_id),
            )

        finally:
            elapsed = time.perf_counter() - start
            logger.info(
                profile.finished_log_event,
                session_id=str(session_id),
                duration=round(elapsed, 4),
            )
            await self._finalize_stats(base_config, global_context, trace_id, session_id)

    def _process_token_usage_stats(
        self,
        base_config: dict | None,
        values: dict | None,
        global_context: GlobalContext,
    ) -> None:
        if base_config is None:
            return None

        token_usage_ctx = ChatTokenUsageContext.get()

        if token_usage_ctx and values:
            # langgraph state로부터 rerank 횟수 추출
            rerank_count = values.get("rerank_count", 0)
            token_usage_ctx.rerank_count = rerank_count

        if (
            token_usage_ctx
            and token_usage_ctx.token_breakdown
            and token_usage_ctx.message_id
        ):
            emit_chat_token_usage_event(
                user_id=global_context.user.id,
                workspace_id=global_context.workspace.id,
                company_id=global_context.company.id,
            )

    async def _update_langfuse_rerank_metadata(
        self,
        client,
        trace_id: str | None,
        values: dict | None,
    ) -> None:
        if not trace_id or not values:
            return

        rerank_metadata = values.get("rerank_metadata")
        if not rerank_metadata:
            return

        try:

            def _update_sync():
                # 별도 score_id로 저장하여 사용자 feedback과 분리
                client.create_score(
                    score_id=f"{trace_id}-rerank-stats",
                    name="rerank_stats",
                    trace_id=trace_id,
                    value=rerank_metadata.get("reranker_essential_recall", 0.0),
                    data_type="NUMERIC",
                    comment=str(rerank_metadata),
                )

            await run_in_threadpool(_update_sync)
        except Exception as e:
            logger.warning(
                "failed_to_update_langfuse_metadata", trace_id=trace_id, error=str(e)
            )

    async def _finalize_stats(
        self,
        base_config: dict | None,
        global_context: GlobalContext,
        trace_id: str | None,
        session_id: uuid.UUID,
    ) -> None:
        """스트리밍 종료 후 토큰 사용량 통계와 langfuse 메타데이터를 처리한다."""
        if base_config is not None:
            try:
                lg_current_state = await self._app.aget_state(base_config)
                values = lg_current_state.values
                self._process_token_usage_stats(base_config, values, global_context)

                if settings.ENABLE_LANGFUSE:
                    client = get_langfuse_client()
                    if client:
                        await self._update_langfuse_rerank_metadata(
                            client, trace_id, values
                        )
            except Exception as stats_err:
                logger.warning(
                    "failed_to_process_post_stream_stats",
                    error=str(stats_err),
                    session_id=str(session_id),
                )

        if settings.ENABLE_LANGFUSE:
            client = get_langfuse_client()
            if client:
                await run_in_threadpool(client.flush)

    def _resolve_input_messages(
        self,
        session_id: uuid.UUID,
        query: str,
        lg_current_state: StateSnapshot,
        additional_context: str | None = None,
    ) -> list[BaseMessage]:

        state_values = lg_current_state.values

        has_history_in_graph = (
            state_values
            and "messages" in state_values
            and len(state_values["messages"]) > 0
        )

        if has_history_in_graph or additional_context is not None:
            logger.info(
                "state_retained", context="state_not_empty", session_id=str(session_id)
            )
            input_messages = self._build_current_turn_messages(query=query)

        else:
            logger.info(
                "state_restored_from_db",
                context="state_empty",
                session_id=str(session_id),
            )

            with SessionLocal() as db:
                past_messages = restore_conversation_context(
                    db=db,
                    session_id=session_id,
                )
                input_messages = past_messages + [HumanMessage(content=query)]

        return input_messages

    def _build_current_turn_messages(
        self,
        *,
        query: str,
    ) -> list[BaseMessage]:
        return [HumanMessage(content=query)]

    async def _ensure_chat_room(
        self,
        global_context: GlobalContext,
        session_id: uuid.UUID,
        query: str,
        *,
        is_slack: bool = False,
    ) -> int:
        """
        채팅방이 없다면 세션을 생성한다.
        채팅방 ID를 반환한다.
        """

        def _get_chat_room_sync():
            with SessionLocal() as db:
                if is_slack:
                    room = get_chat_room_by_session_id(db=db, session_id=session_id)
                else:
                    room = get_chat_room(
                        db=db, session_id=session_id, user_id=global_context.user.id
                    )
                return room.id if room else None

        room_id = await run_in_threadpool(_get_chat_room_sync)

        if room_id:
            return room_id

        initial_title = await generate_chat_room_title(
            global_context=global_context, query=query
        )

        def _create_room_sync():
            with SessionLocal() as db:
                new_room = create_chat_room(
                    db=db,
                    session_id=session_id,
                    user_id=global_context.user.id,
                    workspace_id=global_context.workspace.id,
                    title=initial_title,
                )
                db.commit()
                db.refresh(new_room)
                return new_room.id

        return await run_in_threadpool(_create_room_sync)

    async def _save_message_content(
        self,
        room_id: int,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
        trace_id: str | None = None,
        user_id: int | None = None,
        pipeline_result: list[dict] | None = None,
    ) -> int:
        def _save_sync():
            with SessionLocal() as db:
                message = add_message(
                    db=db,
                    room_id=room_id,
                    role=role,
                    content=content,
                    sources=sources,
                    trace_id=trace_id,
                    user_id=user_id,
                    pipeline_result=pipeline_result,
                )
                db.commit()
                db.refresh(message)
                return message.id

        return await run_in_threadpool(_save_sync)

    async def reset_last_turn(
        self,
        room_id: int,
        session_id: uuid.UUID,
    ) -> str | None:
        """
        마지막 대화 턴을 soft-delete 하고, 해당 세션 id에 대한 Redis Checkpointer를 초기화 한다.
        삭제된 질문 텍스트를 반환한다.
        """

        def _soft_delete_last_turn_sync():
            with SessionLocal() as db:
                deleted_message: str = soft_delete_last_conversation_turn(
                    db=db, room_id=room_id
                )
                db.commit()
                return deleted_message

        deleted_query = await run_in_threadpool(_soft_delete_last_turn_sync)

        if deleted_query:
            checkpointer = get_langgraph_checkpointer()

            await checkpointer.adelete_thread(thread_id=str(session_id))

            logger.info("langgraph_checkpointer_flushed", session_id=str(session_id))

        return deleted_query

    async def _save_partial_if_any(
        self,
        processor: ChatStreamProcessor | None,
        room_id: int,
        trace_id: str | None,
    ) -> None:
        """취소 시점까지 누적된 내용이 있으면 partial로 저장한다."""
        if processor is None:
            return
        content = processor.context.accumulated_content.strip()
        if not content:
            return

        pipeline_result: list[dict] = [
            {"partial": True, "cancelled_at": datetime.now(timezone.utc).isoformat()}
        ]
        if processor.context.pipeline_events:
            pipeline_result.extend(processor.context.pipeline_events)

        sources = processor.context.accumulated_sources or None

        await self._save_message_content(
            room_id=room_id,
            role="assistant",
            content=content,
            sources=sources,
            trace_id=trace_id,
            pipeline_result=pipeline_result,
        )
        logger.info(
            "partial_content_saved",
            room_id=room_id,
            content_length=len(content),
        )

    @observe(name="chat-run-background")
    async def run_background(
        self,
        global_context: GlobalContext,
        prompt_settings: PromptSettings,
        session_id: uuid.UUID,
        event_store: ChatEventStore,
        tool_filters: list[SourceType] | None = None,
        query: str | None = None,
        additional_context: str | None = None,
        mode: Literal["fast", "standard"] = "standard",
        is_slack: bool = False,
    ) -> None:
        """SSE와 독립된 백그라운드 태스크로 그래프를 실행하고 이벤트를 Redis에 발행한다."""

        async def sink(event: StreamEvent) -> None:
            await event_store.publish(str(session_id), event)

        try:
            await self.run(
                global_context,
                prompt_settings,
                session_id,
                sink,
                profile=BACKGROUND_RUN_PROFILE,
                tool_filters=tool_filters,
                query=query,
                additional_context=additional_context,
                mode=mode,
                is_slack=is_slack,
            )
        finally:
            try:
                await event_store.publish_done(str(session_id))
            except Exception:
                logger.exception(
                    "publish_done_failed",
                    session_id=str(session_id),
                )

    def _setup_config(
        self,
        session_id: uuid.UUID,
    ) -> tuple[dict, dict, Any]:
        base_config = {"configurable": {"thread_id": session_id}}
        invoke_config = {**base_config, "recursion_limit": 50}
        trace_id = None

        if settings.ENABLE_LANGFUSE:
            from langfuse.langchain import CallbackHandler

            from catchup.observability.langfuse.configs import get_langfuse_client

            if client := get_langfuse_client():
                trace_id = client.get_current_trace_id()
                logger.debug("langfuse_trace_id", trace_id=trace_id)
                invoke_config["callbacks"] = [
                    CallbackHandler(trace_context={"trace_id": trace_id})
                ]

        return base_config, invoke_config, trace_id

    async def chat(
        self,
        global_context: GlobalContext,
        query: str,
        session_id: uuid.UUID,
    ) -> ChatResponse:
        """Deprecated"""
        app = self._get_app()

        base_config, invoke_config, _ = self._setup_config(session_id)

        inputs = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
            "global_context": global_context,
        }

        start = time.perf_counter()
        final_state = await app.ainvoke(inputs, invoke_config)
        end = time.perf_counter()

        elapsed_time = end - start

        last_message = final_state["messages"][-1]
        sources = final_state.get("sources", [])

        answer_text = (
            last_message.content
            if hasattr(last_message, "content")
            else "답변을 생성하지 못했습니다."
        )

        return ChatResponse(
            answer=answer_text, sources=sources, process_time=elapsed_time
        )
