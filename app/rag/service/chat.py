import asyncio
import logging
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage
from langfuse import observe

from app.rag.graph import get_compiled_graph
from app.rag.models.dto import (
    ChatResponse,
    ChatStreamingFinalResponse,
    ChatStreamingKeepAliveResponse,
    ChatStreamingResponse,
)

logger = logging.getLogger(__name__)

NODE_STATUS_MAP = {
    "router": "질문을 분석하고 있습니다...",
    "rewrite": "질문을 최적화하고 있습니다...",
    "chitchat": "답변을 생성하고 있습니다...",
    "plan": "검색 계획을 수립하고 있습니다...",
    "retrieve": "지식 저장소(GitHub, Jira)를 검색 중입니다...",
    "rerank": "관련성 높은 문서를 선별 중입니다...",
    "github_pr_mcp": "Pull Request 분석을 위해 필요한 데이터를 불러오는 중입니다.",
    "grade": "검색 품질을 검수하고 있습니다...",
    "generate": "최종 답변을 생성하고 있습니다...",
}


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

    @observe()
    async def chat(
        self, query: str, role: str, session_id: str, index_list: list[str]
    ) -> ChatResponse:
        app = await self._get_app()

        inputs = {
            "messages": [HumanMessage(content=query)],
            "role": role,
            "index_list": index_list,
        }

        config = {"configurable": {"thread_id": session_id}}

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

    @observe()
    async def chat_stream(
        self, query: str, role: str, session_id: str, index_list: list[str]
    ) -> AsyncGenerator[dict, None]:
        # Compiled Graph
        app = await self._get_app()

        # Graph 입력 값
        inputs = {
            "messages": [HumanMessage(content=query)],
            "role": role,
            "index_list": index_list,
        }

        # Checkpointer 설정
        config = {"configurable": {"thread_id": session_id}}

        # 실행 시간 측정 시작
        start = time.perf_counter()

        # 마지막으로 Ping 보낸 시각
        last_ping_time = time.perf_counter()

        try:
            async for event in app.astream_events(inputs, config, version="v2"):
                kind = event["event"]  # 이벤트 종류
                name = event["name"]  # 이벤트 이름

                # 각 노드에 진입할 때마다 반환
                if kind == "on_chain_start" and name in NODE_STATUS_MAP:
                    yield ChatStreamingResponse(
                        type="status", node=name, message=NODE_STATUS_MAP[name]
                    ).model_dump()

                # Keep-alive
                elif (
                    kind == "on_chat_model_stream"
                    and event["metadata"].get("langgraph_node") == "generate"
                ):
                    current_time = time.perf_counter()

                    # 최소 1초 간격으로 ping을 보냄
                    if current_time - last_ping_time > 1.0:
                        yield ChatStreamingKeepAliveResponse(type="ping").model_dump()

                        last_ping_time = current_time

                # generate node 종료 시점에 수행할 작업
                elif kind == "on_chain_end" and name == "generate":
                    end = time.perf_counter()
                    elapsed_time = end - start

                    # 최종 상태 획득
                    node_output = event["data"].get("output")

                    if node_output:
                        last_message = node_output["messages"][-1]
                        answer_text = last_message.content
                        sources = node_output.get("sources", [])

                        yield ChatStreamingFinalResponse(
                            type="result",
                            node=name,
                            answer=answer_text,
                            sources=sources,
                            process_time=elapsed_time,
                        ).model_dump()

        except asyncio.CancelledError:
            logger.warning("클라이언트 연결이 종료되었습니다.")
            raise

        finally:
            logger.info(f"Streaming 종료. ===> {elapsed_time:.4f}s")
