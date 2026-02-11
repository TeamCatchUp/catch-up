import asyncio
import logging
import time
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage

from catchup.configs.config import settings
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
from catchup.utils.redis import get_langgraph_checkpointer

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

    async def chat(self, query: str, role: str, session_id: str) -> ChatResponse:
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
        global_context: GlobalContext,
        session_id: str,
        query: str = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        
        # Compiled Graph
        app = await self._get_app()

        # Checkpointer 설정
        config = self._setup_config(session_id)
        
        inputs = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
            "global_context": global_context
        }

        # 실행 시간 측정 시작
        start = time.perf_counter()
        
        stream_state = {
            "buffer": "",
            "is_citation_reached": False
        }

        try:
            async for event in app.astream_events(inputs, config, version="v2"):
                async for parsed_event in self._parse_stream_event(event, session_id, stream_state):
                    yield parsed_event

        except asyncio.CancelledError:
            logger.warning(f"({session_id})클라이언트 연결 종료.")
            raise

        except Exception as e:
            logger.error(f"({session_id})Streaming 중 에러 발생: {e}", exc_info=True)

        finally:
            elapsed_time = time.perf_counter() - start
            logger.info(f"({session_id})Streaming 종료: total {elapsed_time:.4f}s")

    async def _parse_stream_event(
        self,
        event: dict[str, Any],
        session_id: str,
        stream_state: dict[str, Any]
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
            async for res in self._handle_node_end(event, session_id):
                yield res
    
    async def _handle_node_start(
        self,
        event: dict,
        session_id: str
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
        session_id: str,
        stream_state: dict
    ): 
        """토큰 스트리밍"""
        chunk = event["data"].get("chunk")
        node = event["metadata"].get("langgraph_node")
        
        # 타겟 노드가 아니거나 컨텐츠가 없으면 스킵
        is_target_node = node in ("chitchat", "generate_final_answer")
        if not (is_target_node and chunk and chunk.content):
            return

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
            session_id: str
        ):
        """
            그래프 종료 시점.
            인용 사유를 포함한 최종 소스를 업데이트한다.
        """
        name = event["name"]
        
        if name == "generate_final_answer":
            output = event["data"].get("output")
            # 결과에 sources가 포함되어 있다면 전송 (JSON 파싱 성공 시)
            if output and isinstance(output, dict) and "sources" in output:
                final_sources = output["sources"]
                if final_sources:
                    logger.info("Sending final sources with rationale.")
                    yield ChatStreamingSourceResponse(
                        session_id=session_id, sources=final_sources
                    )

    def _setup_config(self, session_id: str):
        default_config = {"configurable": {"thread_id": session_id}}
        if settings.ENABLE_LANGFUSE:
            from catchup.observability.langfuse import langfuse_handler
            default_config["callbacks"] = [langfuse_handler]
            logger.info(f"Langfuse Status: {settings.ENABLE_LANGFUSE}, Handler: {langfuse_handler is not None}")

        return default_config
        