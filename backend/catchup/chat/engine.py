import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Optional
import uuid

from fastapi.concurrency import run_in_threadpool
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.pregel.types import StateSnapshot
from sqlalchemy.orm import Session

from catchup.chat.chat_room import generate_chat_room_title
from catchup.chat.utils import restore_conversation_context
from catchup.configs.config import settings
from catchup.db.chat_room import add_message, create_chat_room, get_chat_room, soft_delete_last_conversation_turn
from catchup.db.models import ChatRoom, SourceType
from catchup.observability.langfuse import observe
from catchup.chat.schemas import (
    NODE_STATUS_MAP,
    ChatResponse,
    ChatStreamingSourceResponse,
    ChatStreamingStatusResponse,
    ChatStreamingTokenResponse,
    StreamEvent,
)
from catchup.rag.graph import get_compiled_graph
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.sources import BaseSource
from catchup.rag.checkpoint import get_langgraph_checkpointer

logger = logging.getLogger(__name__)


class ChatService:
    # Compiled Graph
    _app = None

    def __init__(self):
        pass

    async def _get_app(self):
        # 싱글톤
        if ChatService._app is None:
            checkpointer = get_langgraph_checkpointer()
            ChatService._app = get_compiled_graph(checkpointer)
        return ChatService._app

    @observe(name="chat-stream")
    async def chat_stream(
        self,
        db: Session,
        global_context: GlobalContext,
        session_id: uuid.UUID,
        tool_filters: Optional[list[SourceType]] = None,
        query: str = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        
         # 실행 시간 측정 시작
        start = time.perf_counter()
            
        try:
            # 채팅 세션 획득
            room_id: int = await self._setup_chat_room(
                db,
                global_context,
                session_id,
                query
            )
            
            # Compiled Graph
            app = await self._get_app()

            # Checkpointer 설정
            config = self._setup_config(session_id)
            
            lg_current_state = await app.aget_state(config)
            
            input_messages = await run_in_threadpool(
                self._resolve_input_messages,
                db,
                session_id,
                query,
                lg_current_state
            )
                        
            # 초기 AgentState
            inputs = {
                "messages": input_messages,
                "original_query": query,
                "global_context": global_context,
                "tool_filters": tool_filters,
            }
            
            stream_state = {
                "buffer": "",
                "is_citation_reached": False,
                "has_streamed": False
            }

            async for event in app.astream_events(inputs, config, version="v2"):
                async for parsed_event in self._parse_stream_event(event, session_id, room_id, stream_state, db):
                    yield parsed_event

        except asyncio.CancelledError:
            logger.warning(f"({session_id}) 답변 생성이 중지되었습니다.")
            raise

        except Exception as e:
            logger.error(f"({session_id})Streaming 중 에러 발생: {e}", exc_info=True)
            
            room = await run_in_threadpool(
                get_chat_room,
                db,
                session_id,
                global_context.user.id
            )
            
            if room:
                await self.reset_last_turn(
                    db,
                    room
                )
            else:
                logger.warning(f"({session_id}) 에러 발생 후 복구를 시도했으나 채팅방을 찾을 수 없습니다.")
                
            

        finally:
            elapsed_time = time.perf_counter() - start
            logger.info(f"({session_id})Streaming 종료: total {elapsed_time:.4f}s")
            
    def _resolve_input_messages(
        self,
        db: Session,
        session_id: uuid.UUID,
        query: str,
        lg_current_state: StateSnapshot
    ) -> list[BaseMessage]:
        
        state_values = lg_current_state.values

        has_history_in_graph = (
            state_values
            and "messages" in state_values
            and len(state_values["messages"]) > 0
        )
        
        if has_history_in_graph:
            logger.info(f"({session_id}) State not empty: appending new query.")
            input_messages = [HumanMessage(content=query)]
        else:
            logger.info(f"({session_id}) State empty: restoring context from DB.")
            past_messages = restore_conversation_context(
                db=db,
                session_id=session_id
            )
            input_messages = past_messages + [HumanMessage(content=query)]
            
        return input_messages

    async def _parse_stream_event(
        self,
        event: dict[str, Any],
        session_id: uuid.UUID,
        room_id: int,
        stream_state: dict[str, Any],
        db: Session
    ) -> AsyncGenerator[StreamEvent, None]:
        kind = event["event"]  # 이벤트 종류
        name = event["name"]  # 이벤트 이름
        
        # 최종 답변에서 인용구가 발견된 경우 스트리밍 차단
        if stream_state.get("is_citation_reached", False):
            # generate_final_answer 노드 종료 이벤트 외에는 전부 차단
            if not (kind == "on_chain_end" and name == "generate_final_answer"):
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
            async for res in self._handle_node_end(event, session_id, room_id, stream_state, db):
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
        if name == "generate_final_answer":
            input_data = event["data"].get("input", {})
            docs = input_data.get("retrieved_docs", [])
            logger.info(f"Initial docs count: {len(docs)}")

            sources = [
                BaseSource.from_document(index=i, doc=doc)
                for i, doc in enumerate(docs, start=1)
            ]
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
        is_target_node = node in ("chitchat", "generate_final_answer")
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
            db: Session
        ):
        """
            그래프 종료 시점.
            인용 사유를 포함한 최종 소스를 업데이트한다.
        """
        
        target_nodes = ("chitchat", "generate_final_answer")
        
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
        
        if final_content:
            await self._save_message_content(
                db,
                room_id,
                "assistant",
                final_content,
                final_sources_data
            )
            logger.info(f"({session_id}) Final answer & sources saved to DB.")
        
        # case 1: Fallback 처리: 모델 자체 스트리밍 없이 종료된 경우 메시지 내용 전송
        if not stream_state.get("has_streamed", False):
            messages = output.get("messages", [])
            if messages:
                last_msg = messages[-1]
                fallback_content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                logger.warning("Fallback Answer 전송 (Streaming 미감지)")
                yield ChatStreamingTokenResponse(
                    session_id=session_id,
                    token=fallback_content
                )
        
        # case 2: 인용 사유를 포함한 최종 소스 전송
        if "sources" in output:
            final_sources = output["sources"]
            if final_sources:
                logger.info("Sending final sources with rationale.")
                yield ChatStreamingSourceResponse(
                    session_id=session_id, sources=final_sources
                )
                        
    async def _setup_chat_room(
        self,
        db: Session,
        global_context: GlobalContext,
        session_id: uuid.UUID,
        query: str
    ) -> int:
        """
            채팅방이 없다면 세션을 생성한다.
            사용자 쿼리를 저장한다.
            채팅방 ID를 반환한다.
        """

        room = await run_in_threadpool(
            get_chat_room, 
            db, 
            session_id, 
            global_context.user.id
        )
        
        if not room:
            initial_title = await generate_chat_room_title(query)
               
            # 새로운 채팅 세션일 경우
            def _create_room_sync():
                new_room = create_chat_room(
                    db=db,
                    session_id=session_id,
                    user_id=global_context.user.id,
                    workspace_id=global_context.workspace.id,
                    title=initial_title
                )
                db.commit()
                db.refresh(new_room)
                return new_room
        
            room = await run_in_threadpool(_create_room_sync)     
               
        # 사용자 쿼리 저장
        await self._save_message_content(
            db,
            room.id,
            "user",
            query
        )
        
        return room.id
    
    async def _save_message_content(
        self,
        db: Session,
        room_id: int,
        role: str,
        content: str,
        sources: Optional[list[dict[str, Any]]] = None
    ):
        
        def _save_sync():
            add_message(
                db=db,
                room_id=room_id,
                role=role,
                content=content,
                sources=sources
            )
            db.commit()
            
        await run_in_threadpool(_save_sync)
        
    async def reset_last_turn(
        self,
        db: Session,
        room: ChatRoom,
    ) -> Optional[str]:
        """
        마지막 대화 턴을 soft-delete 하고, 해당 세션 id에 대한 Redis Checkpointer를 초기화 한다.
        삭제된 질문 텍스트를 반환한다.
        """
        
        def _soft_delete_last_turn_sync():
            deleted_message = soft_delete_last_conversation_turn(
                db=db,
                room_id=room.id
            )
            db.commit()
            return deleted_message
        
        deleted_query = await run_in_threadpool(_soft_delete_last_turn_sync)
        
        if deleted_query:
            checkpointer = get_langgraph_checkpointer()
            
            await checkpointer.adelete_thread(
                thread_id=str(room.session_id)
            )
            
            logger.info(f"Session {room.session_id}: LangGraph memory & Legacy history flushed.")
        
        return deleted_query
    
    def _setup_config(self, session_id: uuid.UUID):
        default_config = {"configurable": {"thread_id": session_id}}
        if settings.ENABLE_LANGFUSE:
            from catchup.observability.langfuse import langfuse_handler
            default_config["callbacks"] = [langfuse_handler]
            logger.info(f"Langfuse Status: {settings.ENABLE_LANGFUSE}, Handler: {langfuse_handler is not None}")

        return default_config
    
    async def chat(
            self,
            global_context: GlobalContext,
            query: str,
            session_id: uuid.UUID,
    ) -> ChatResponse:
        """Deprecated"""
        app = await self._get_app()

        config = self._setup_config(session_id)
        
        inputs = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
            "global_context": global_context
        }

        start = time.perf_counter()
        final_state = await app.ainvoke(inputs, config)
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
        