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
from langgraph.pregel.types import StateSnapshot

from catchup.audit.actions import ChatAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import ChatAuditMetadata
from catchup.chat.chat_room import generate_chat_room_title
from catchup.chat.schemas import NODE_STATUS_MAP
from catchup.chat.schemas import ChatResponse
from catchup.chat.schemas import ChatStreamingSourceResponse
from catchup.chat.schemas import ChatStreamingStatusResponse
from catchup.chat.schemas import ChatStreamingTokenResponse
from catchup.chat.schemas import StreamEvent
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
from catchup.rag.schemas.sources import BaseSource

logger = structlog.get_logger()

# Langfuse
observe = get_observe()

class ChatService:
    # Compiled Graph
    _app = None

    def __init__(self):
        if settings.ENABLE_LANGFUSE:
            logger.info(
                "langfuse_initialized",
                host=settings.LANGFUSE_BASE_URL,
                active=True
            )

    async def _get_app(self):
        # 싱글톤
        if ChatService._app is None:
            checkpointer = get_langgraph_checkpointer()
            ChatService._app = get_compiled_graph(checkpointer)
        return ChatService._app

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
            
        try:            
            # 채팅 세션 획득
            room_id: int = await self._setup_chat_room(
                global_context,
                session_id,
                query,
                is_slack=is_slack,
            )

            # Compiled Graph
            app = await self._get_app()

            # Checkpointer 설정
            base_config, invoke_config, trace_id = self._setup_config(session_id)

            # 단순 state 조회는 langfuse에 빈 trace를 남길 필요가 없으므로 base_config 주입
            lg_current_state = await app.aget_state(base_config)
            
            input_messages = await run_in_threadpool(
                self._resolve_input_messages,
                session_id,
                query,
                lg_current_state,
                additional_context,
            )

            # 초기 AgentState
            inputs = {
                # 사용자 변수
                "messages": input_messages,
                "original_query": query,
                "global_context": global_context,
                "tool_filters": tool_filters,
                "prompt_settings": prompt_settings,
                "mode": mode,

                # RAG 파이프라인 상태 변수
                "retry_count": 0,
                "grade_comment": None,
                "grade_status": None,
                "vector_search_queries": [],
                "graph_search_queries": [],
                "retrieved_docs": [],

                # 비용 변수
                "token_breakdown": {},
                "rerank_count": 0,
            }
            
            stream_state = {
                "buffer": "",
                "is_citation_reached": False,
                "has_streamed": False,
                "langfuse_trace_id": trace_id
            }

            async for event in app.astream_events(inputs, invoke_config, version="v2"):
                async for parsed_event in self._parse_stream_event(event, session_id, room_id, stream_state):
                    yield parsed_event

        except asyncio.CancelledError:
            emit_audit_event(
                action=ChatAction.GENERATE_RESPONSE,
                status=AuditStatus.FAILURE,
                level=AuditLevel.WARNING,
                metadata=ChatAuditMetadata(
                    context="connection_cancelled",
                    session_id=session_id,
                )
            )
            raise

        except Exception as e:
            logger.exception("streaming_error")

            def _get_chat_room_sync():
                with SessionLocal() as db:
                    if is_slack:
                        room = get_chat_room_by_session_id(db=db, session_id=session_id)
                    else:
                        room = get_chat_room(db=db, session_id=session_id, user_id=global_context.user.id)
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
                    session_id=str(session_id)
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
                duration=round(elapsed, 4)
            )
            
            if base_config is not None:
                token_usage_ctx = ChatTokenUsageContext.get()
                lg_current_state = await self._app.aget_state(base_config)
                values = lg_current_state.values

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

        if has_history_in_graph:
            logger.info(
                "state_retained",
                context="state_not_empty",
                session_id=str(session_id)
            )
            input_messages = self._build_current_turn_messages(
                query=query,
                additional_context=additional_context,
            )

        elif additional_context is not None:
            logger.info(
                "state_injected_from_context",
                context="additional_context_provided",
                session_id=str(session_id)
            )
            input_messages = self._build_current_turn_messages(
                query=query,
                additional_context=additional_context,
            )

        else:
            logger.info(
                "state_restored_from_db",
                context="state_empty",
                session_id=str(session_id)
            )

            with SessionLocal() as db:
                past_messages = restore_conversation_context(
                    db=db,
                    session_id=session_id
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

    async def _parse_stream_event(
        self,
        event: dict[str, Any],
        session_id: uuid.UUID,
        room_id: int,
        stream_state: dict[str, Any],
    ) -> AsyncGenerator[StreamEvent, None]:
        kind = event["event"]  # 이벤트 종류
        name = event["name"]  # 이벤트 이름
        
        # 최종 답변에서 인용구가 발견된 경우 스트리밍 차단
        if stream_state.get("is_citation_reached", False):
            # generate_final_answer 노드 종료 이벤트 외에는 전부 차단
            if not (kind == "on_chain_end" and name in ("generate_final_answer", "generate_final_answer_fast")):
                return

        # 1. 노드 시작
        if kind == "on_chain_start":
            async for res in self._handle_node_start(event, session_id):
                yield res
                
        # 2. 토큰 스트리밍 처리
        elif kind == "on_chat_model_stream":
            async for res in self._handle_token_stream(event, session_id, stream_state):
                yield res

        # 3. 노드 종료 (현재는 최종 답변 생성 노드만 관여)
        elif kind == "on_chain_end":
            async for res in self._handle_node_end(event, session_id, room_id, stream_state):
                yield res
    
    async def _handle_node_start(
        self,
        event: dict,
        session_id: uuid.UUID
    ):
        """노드 단위 답변 생성 과정 스트리밍"""
        name = event["name"]
        
        if name in NODE_STATUS_MAP:
            yield ChatStreamingStatusResponse(
                session_id=session_id, node=name, message=NODE_STATUS_MAP[name]
            )

        # 답변 생성 노드 시작 시: 초기 출처 후보 목록 전송
        if name in ("generate_final_answer", "generate_final_answer_fast"):
            input_data = event["data"].get("input", {})
            docs = input_data.get("retrieved_docs", [])
            sources = [
                BaseSource.from_document(index=i, doc=doc)
                for i, doc in enumerate(docs, start=1)
            ]
            emit_audit_event(
                action=ChatAction.PROVIDE_SOURCES,
                status=AuditStatus.SUCCESS,
                level=AuditLevel.INFO,
                metadata=ChatAuditMetadata(
                    session_id=session_id,
                    provided_sources_count=len(sources),
                    provided_source_ids=[src.id for src in sources]
                ),
            )
            
            yield ChatStreamingSourceResponse(session_id=session_id, sources=sources)
            
    async def _handle_token_stream(
        self,
        event: dict,
        session_id: uuid.UUID,
        stream_state: dict
    ): 
        """토큰 스트리밍"""
        chunk = event["data"].get("chunk")
        node = event["metadata"].get("langgraph_node")
        
        # 타겟 노드가 아니거나 컨텐츠가 없으면 스킵
        is_target_node = node in ("chitchat", "generate_final_answer", "generate_final_answer_fast")
        if not (is_target_node and chunk and chunk.content):
            return
        
        stream_state["has_streamed"] = True

        token = chunk.content
        
        # 사용자에게 출처 인용 정보가 담긴 XML 태그가 노출되지 않도록 검증하기 위한 토큰 버퍼
        current_buffer = stream_state.get("buffer", "") + token
        TARGET_TAG = "<citations>"

        # case 1: <citations 태그 발견 -> 즉시 스트리밍 중단 및 앞부분만 전송
        if "<citations" in current_buffer:
            stream_state["is_citation_reached"] = True
            clean_content = current_buffer.split("<citations")[0]
            if clean_content:
                yield ChatStreamingTokenResponse(session_id=session_id, token=clean_content)
            return

        # case 2: '<' 포함 -> 버퍼링 여부 결정
        if "<" in current_buffer:
            last_angle_idx = current_buffer.rfind("<")
            safe_part = current_buffer[:last_angle_idx]
            suspicious_part = current_buffer[last_angle_idx:]

            # 의심되는 부분이 태그의 앞 부분과 일치하는지 여부 확인 "<c", "<cit"
            if TARGET_TAG.startswith(suspicious_part):
                if safe_part:
                    yield ChatStreamingTokenResponse(session_id=session_id, token=safe_part)
                # 의심스러운 뒷부분만 버퍼에 남김
                stream_state["buffer"] = suspicious_part
                return

        # case 3: 일반 텍스트 -> 전송 & 버퍼 초기화 
        yield ChatStreamingTokenResponse(session_id=session_id, token=current_buffer)
        stream_state["buffer"] = ""
        
    async def _handle_node_end(
            self,
            event: dict,
            session_id: uuid.UUID,
            room_id: int,
            stream_state: dict,
        ):
        """
            그래프 종료 시점.
            인용 사유를 포함한 최종 소스를 업데이트한다.
        """
        
        target_nodes = ("chitchat", "generate_final_answer", "generate_final_answer_fast")
        
        if event["name"] not in target_nodes:
            return
        
        output = event["data"].get("output")
        if not (output and isinstance(output, dict)):
            return
        
        messages = output.get("messages", [])
        sources = output.get("sources", [])
        
        last_msg = messages[-1] if messages else None
        final_content = last_msg.content if last_msg and hasattr(last_msg, "content") else str(last_msg)
        
        final_sources_data = [
            source.model_dump(mode='json') if hasattr(source, "model_dump") else source
            for source in sources
        ]
        
        trace_id = stream_state.get("langfuse_trace_id")
        
        if final_content:
            message_id = await self._save_message_content(
                room_id,
                "assistant",
                final_content,
                final_sources_data,
                trace_id
            )
            
            token_usage_ctx = ChatTokenUsageContext.get()
            if token_usage_ctx and message_id:
                token_usage_ctx.message_id = message_id
            
            logger.info(
                "final_contents_saved", 
                session_id=str(session_id)
            )
        
        # case 1: Fallback 처리: 모델 자체 스트리밍 없이 종료된 경우 메시지 내용 전송
        if not stream_state.get("has_streamed", False):
            messages = output.get("messages", [])
            if messages:
                last_msg = messages[-1]
                fallback_content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                logger.warning(
                    "fallback_answer_sent", 
                    context="no_streaming_event",
                    session_id=str(session_id)
                )
                
                yield ChatStreamingTokenResponse(
                    session_id=session_id,
                    token=fallback_content
                )
        
        # case 2: 인용 사유를 포함한 최종 소스 전송
        if "sources" in output:
            final_sources = output["sources"]
            if final_sources:
                logger.info(
                    "final_sources_sent",
                    session_id=str(session_id)
                )
                yield ChatStreamingSourceResponse(
                    session_id=session_id, sources=final_sources
                )
                        
    async def _setup_chat_room(
        self,
        global_context: GlobalContext,
        session_id: uuid.UUID,
        query: str,
        *,
        is_slack: bool = False,
    ) -> int:
        """
            채팅방이 없다면 세션을 생성한다.
            사용자 쿼리를 저장한다.
            채팅방 ID를 반환한다.
        """

        def _get_chat_room_sync():
            with SessionLocal() as db:
                if is_slack:
                    room = get_chat_room_by_session_id(db=db, session_id=session_id)
                else:
                    room = get_chat_room(db=db, session_id=session_id, user_id=global_context.user.id)
                return room.id if room else None
        room_id = await run_in_threadpool(_get_chat_room_sync)

        if not room_id:
            initial_title = await generate_chat_room_title(
                global_context=global_context,
                query=query
            )

            # 새로운 채팅 세션일 경우
            def _create_room_sync():
                with SessionLocal() as db:
                    new_room = create_chat_room(
                        db=db,
                        session_id=session_id,
                        user_id=global_context.user.id,
                        workspace_id=global_context.workspace.id,
                        title=initial_title
                    )
                    db.commit()
                    db.refresh(new_room)
                    return new_room.id
            room_id = await run_in_threadpool(_create_room_sync)

        # 사용자 쿼리 저장 (실제 요청자 귀속)
        await self._save_message_content(
            room_id,
            "user",
            query,
            user_id=global_context.user.id,
        )

        return room_id
    
    async def _save_message_content(
        self,
        room_id: int,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
        trace_id: str | None = None,
        user_id: int | None = None,
    ):
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
                    db=db,
                    room_id=room_id
                )
                db.commit()
                return deleted_message
            
        deleted_query = await run_in_threadpool(_soft_delete_last_turn_sync)
        
        if deleted_query:
            checkpointer = get_langgraph_checkpointer()
            
            await checkpointer.adelete_thread(
                thread_id=str(session_id)
            )
            
            logger.info(
                "langgraph_checkpointer_flushed",
                session_id=str(session_id)
            )

        return deleted_query
    
    def _setup_config(
        self, 
        session_id: uuid.UUID,
    ) -> tuple[dict, dict, Any]:
        base_config = {"configurable": {"thread_id": session_id}}
        invoke_config = {**base_config}
        trace_id = None
        
        if settings.ENABLE_LANGFUSE:
            from langfuse import Langfuse
            from langfuse.langchain import CallbackHandler

            from catchup.observability.langfuse.configs import get_langfuse_client
            
            if get_langfuse_client():
                trace_id = Langfuse.create_trace_id()
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
        app = await self._get_app()

        base_config, invoke_config, _ = self._setup_config(session_id)

        
        inputs = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
            "global_context": global_context
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
        