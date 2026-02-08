import asyncio
import logging
import time
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage
from langfuse import observe

from catchup.observability.langfuse_client import langfuse_handler
from catchup.configs.config import settings
from catchup.chat.schemas import (
    NODE_STATUS_MAP,
    ChatResponse,
    ChatStreamingSourceResponse,
    ChatStreamingStatusResponse,
    ChatStreamingTokenResponse,
    StreamEvent,
)
from catchup.rag.graph import get_compiled_graph

logger = logging.getLogger(__name__)


class ChatService:
    # Compiled Graph
    _app = None

    def __init__(self):
        pass

    async def _get_app(self):
        # 싱글톤
        if ChatService._app is None:
            ChatService._app = await get_compiled_graph()
        return ChatService._app

    @observe(name="chat")
    async def chat(
        self, query: str, role: str, session_id: str
    ) -> ChatResponse:
        app = await self._get_app()
        
        config = self._setup_config(session_id)
        
        inputs = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
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

    @observe(name="chat-stream")
    async def chat_stream(
        self,
        session_id: str,
        query: str = None,
        role: str = "user",
    ) -> AsyncGenerator[StreamEvent, None]:
        # Compiled Graph
        app = await self._get_app()

        # Checkpointer 설정
        config = self._setup_config(session_id)
        
        inputs = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
        }
        
        # 실행 시간 측정 시작
        start = time.perf_counter()

        try:
            async for event in app.astream_events(inputs, config, version="v2"):
                async for parsed_event in self._parse_stream_event(event, session_id):
                    yield parsed_event

        except asyncio.CancelledError:
            logger.warning(f"({session_id})클라이언트 연결 종료.")
            raise
        
        except Exception as e:
            logger.error(f"({session_id})Streaming 중 에러 발생: {e}" , exc_info=True)
        
        finally:
            elapsed_time = time.perf_counter() - start
            logger.info(f"({session_id})Streaming 종료: total {elapsed_time:.4f}s")

    async def _parse_stream_event(
        self,
        event: dict[str, Any],
        session_id: str
    ) -> AsyncGenerator[StreamEvent, None]:
        kind = event["event"]  # 이벤트 종류
        name = event["name"]  # 이벤트 이름

        # 노드 시작 상태 알림
        if kind == "on_chain_start" and name in NODE_STATUS_MAP:
            yield ChatStreamingStatusResponse(
                session_id=session_id,
                node=name,
                message=NODE_STATUS_MAP[name]
            )
            
            if name == "generate_final_answer":
                input_data = event["data"].get("input", {})
                docs = input_data.get("retrieve_docs", [])
                
                sources = []
                # TODO: Source 담아서 보내야 함.
                # if docs:
                #     sources = []
                    
                yield ChatStreamingSourceResponse(
                    session_id=session_id,
                    sources=sources
                )
        
        elif kind == "on_chat_model_stream":
            node = event["metadata"].get("langgraph_node")
            is_final_node = node in ("chitchat", "generate_final_answer")
            chunk = event["data"].get("chunk")
            
            if is_final_node and chunk and chunk.content:
                yield ChatStreamingTokenResponse(
                    session_id=session_id,
                    token=chunk.content  
                )
                
    def _setup_config(self, session_id: str):
        default_config = {"configurable": {"thread_id": session_id}}
        if settings.ENABLE_LANGFUSE:
            default_config["callbacks"] = [langfuse_handler]
        return default_config