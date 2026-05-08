import asyncio
import time
import uuid
from typing import Any
from typing import AsyncGenerator
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
from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.langfuse.configs import get_observe
from catchup.rag.checkpoint import get_langgraph_checkpointer
from catchup.rag.graph import get_compiled_graph
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.prompt_settings import PromptSettings

logger = structlog.get_logger()

# Langfuse
observe = get_observe()

_MODE_CEILING: dict[str, str] = {
    "fast": "standard",
    "standard": "complex",
}


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

    @observe(name="chat-stream")
    async def chat_stream(
        self,
        global_context: GlobalContext,
        prompt_settings: PromptSettings,
        session_id: uuid.UUID,
        tool_filters: list[SourceType] | None = None,
        query: str = None,
        additional_context: str | None = None,
        mode: Literal["fast", "standard"] = "standard",
        is_slack: bool = False,
    ) -> AsyncGenerator[StreamEvent, None]:

        # 실행 시간 측정 시작
        start = time.perf_counter()

        # 채팅 토큰 사용량 컨텍스트 초기화
        ChatTokenUsageContext.init()

        base_config = None
        processor = None
        values = None
        saved_message_id: int | None = None

        try:
            # 채팅방만 보장 (user 메시지 저장은 input_messages 결정 후로 미룸)
            room_id: int = await self._ensure_chat_room(
                global_context,
                session_id,
                query,
                is_slack=is_slack,
            )

            # Compiled Graph
            app = self._get_app()

            # Checkpointer 설정
            base_config, invoke_config, trace_id = self._setup_config(session_id)

            # 단순 state 조회는 langfuse에 빈 trace를 남길 필요가 없으므로 base_config 주입
            lg_current_state = await app.aget_state(base_config)

            # DB 복원 시점에 현재 turn의 user 쿼리가 아직 저장되지 않은 상태여야
            # past_messages + [HumanMessage(query)] 조합에서 중복이 발생하지 않는다.
            input_messages = await run_in_threadpool(
                self._resolve_input_messages,
                session_id,
                query,
                lg_current_state,
                additional_context,
            )

            # 입력 메시지 결정 후 user 쿼리를 DB에 저장 (실제 요청자 귀속)
            # saved_message_id를 추적해 복구 단계에서 이번 턴 저장 여부를 가드한다.
            saved_message_id = await self._save_message_content(
                room_id,
                "user",
                query,
                user_id=global_context.user.id,
            )

            # 초기 AgentState
            inputs = {
                # 사용자 변수
                "messages": input_messages,
                "original_query": query,
                "global_context": global_context,
                "tool_filters": tool_filters,
                "prompt_settings": prompt_settings,
                "max_pipeline_type": _MODE_CEILING.get(mode, "complex"),
                # RAG 파이프라인 상태 변수
                "vector_search_queries": [],
                # retrieved_docs는 의도적으로 초기화하지 않음.
                # reuse 파이프라인이 이전 턴의 retrieved_docs를 재사용해야 하므로
                # 각 서브그래프(simple/standard/complex)에서 직접 덮어쓴다.
                # Agentic RAG 상태 변수
                "agent_iteration": 0,
                "accumulated_docs": [],
                "agent_seen_doc_ids": [],
                "confirmed_essential_doc_ids": [],
                # 비용 변수
                "token_breakdown": {},
                "rerank_count": 0,
            }

            processor = ChatStreamProcessor(
                session_id=session_id,
                room_id=room_id,
                save_message=self._save_message_content,
                langfuse_trace_id=trace_id,
            )

            async for event in app.astream_events(inputs, invoke_config, version="v2"):
                async for parsed_event in processor.process(event):
                    yield parsed_event

        except asyncio.CancelledError:
            elapsed = time.perf_counter() - start
            logger.warning(
                "stream_cancelled",
                session_id=str(session_id),
                elapsed_seconds=round(elapsed, 2),
                cancelled_at_node=processor.context.current_node
                if processor is not None
                else None,
            )
            emit_audit_event(
                action=ChatAction.GENERATE_RESPONSE,
                status=AuditStatus.FAILURE,
                level=AuditLevel.WARNING,
                metadata=ChatAuditMetadata(
                    context="connection_cancelled",
                    session_id=session_id,
                ),
            )
            raise

        except Exception as e:
            logger.exception("streaming_error")

            # 이번 턴의 user 메시지가 실제로 저장된 경우에만 복구를 수행한다.
            if saved_message_id is not None:

                def _get_chat_room_sync():
                    with SessionLocal() as db:
                        if is_slack:
                            room = get_chat_room_by_session_id(
                                db=db, session_id=session_id
                            )
                        else:
                            room = get_chat_room(
                                db=db,
                                session_id=session_id,
                                user_id=global_context.user.id,
                            )
                        return room.id if room else None

                room_id = await run_in_threadpool(_get_chat_room_sync)

                if room_id:
                    await self.reset_last_turn(
                        room_id=room_id,
                        session_id=session_id,
                    )
                else:
                    logger.warning(
                        "chatroom_not_found",
                        context="post_streaming_error",
                        msg="스트리밍 에러 이후 세션 복구 실패",
                        session_id=str(session_id),
                    )

            emit_audit_event(
                action=ChatAction.GENERATE_RESPONSE,
                status=AuditStatus.FAILURE,
                level=AuditLevel.ERROR,
                metadata=ChatAuditMetadata(
                    session_id=session_id,
                    context="streaming_error",
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
                "streaming_finished",
                session_id=str(session_id),
                duration=round(elapsed, 4),
            )

            # base_config가 생성된 경우에만(즉, Graph 호출 시도 후) 후속 처리 진행
            if base_config is not None:
                try:
                    # langgraph state 추출
                    lg_current_state = await self._app.aget_state(base_config)
                    values = lg_current_state.values

                    # 토큰 사용량 처리
                    self._process_token_usage_stats(base_config, values, global_context)

                    # Langfuse 관측 데이터 통합 처리
                    if settings.ENABLE_LANGFUSE:
                        client = get_langfuse_client()
                        if client:
                            await self._update_langfuse_rerank_metadata(
                                client, trace_id, values
                            )
                except Exception as stats_err:
                    # 통계 수집 중 에러가 메인 스트림 에러 처리를 방해하지 않도록 격리 로깅
                    logger.warning(
                        "failed_to_process_post_stream_stats",
                        error=str(stats_err),
                        session_id=str(session_id),
                    )

            if settings.ENABLE_LANGFUSE:
                client = get_langfuse_client()
                if client:
                    await run_in_threadpool(client.flush)

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
                    value=rerank_metadata.get("alignment_score", 0.0),
                    data_type="NUMERIC",
                    comment=str(rerank_metadata),
                )

            await run_in_threadpool(_update_sync)
        except Exception as e:
            logger.warning(
                "failed_to_update_langfuse_metadata", trace_id=trace_id, error=str(e)
            )

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

        if has_history_in_graph:
            logger.info(
                "state_retained", context="state_not_empty", session_id=str(session_id)
            )
            input_messages = self._build_current_turn_messages(
                query=query,
                additional_context=additional_context,
            )

        elif additional_context is not None:
            logger.info(
                "state_injected_from_context",
                context="additional_context_provided",
                session_id=str(session_id),
            )
            input_messages = self._build_current_turn_messages(
                query=query,
                additional_context=additional_context,
            )

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
        additional_context: str | None,
    ) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        if additional_context is not None:
            messages.append(HumanMessage(content=additional_context))
        messages.append(HumanMessage(content=query))
        return messages

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

    def _setup_config(
        self,
        session_id: uuid.UUID,
    ) -> tuple[dict, dict, Any]:
        base_config = {"configurable": {"thread_id": session_id}}
        invoke_config = {**base_config}
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
