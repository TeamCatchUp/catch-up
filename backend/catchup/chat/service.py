import asyncio
import logging
import time
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage
from langfuse import observe
from langgraph.types import Command

from catchup.chat.schemas import (
    ChatResponse,
    ChatStreamingFinalResponse,
    ChatStreamingInterruptResponse,
    ChatStreamingKeepAliveResponse,
    ChatStreamingResponse,
    StreamEvent,
)
from catchup.rag.graph import get_compiled_graph

logger = logging.getLogger(__name__)

NODE_STATUS_MAP = {
    # 1. 초기 분석
    "route": "질문의 성격을 분석하고 있습니다...",
    
    # 2. 질문 재작성
    "rewrite": "검색 정확도를 높이기 위해 질문을 최적화하고 있습니다...",
    
    # 3. 검색 계획 및 실행
    "generate_vector_queries": "최적의 검색 쿼리를 생성하고 있습니다...",
    "search_vector_db": "지식 저장소(Vector DB)에서 문서를 검색 중입니다...",
    "rerank": "검색된 문서들의 관련성을 분석하여 우선순위를 정하고 있습니다...",
    
    # 4. 검수 및 확장
    "grade": "검색 결과가 충분한지 검토하고 있습니다...",
    "expand_graph_context": "지식 그래프를 통해 연관된 정보를 확장 탐색 중입니다...",
    "fetch_details_after_graph_context_expansion": "확장된 정보의 상세 내용을 불러오고 있습니다...",
    
    # 5. 폴백 (Fallback)
    "fallback_cypher_query": "추가적인 그래프 질의(Cypher)를 실행하여 정보를 보완 중입니다...",
    
    # 6. 최종 답변
    "generate_final_answer": "모든 정보를 종합하여 최종 답변을 작성하고 있습니다...",
    
    # (Optional) 일상 대화용
    "chitchat": "답변을 생성하고 있습니다...",
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
        self, query: str, role: str, session_id: str
    ) -> ChatResponse:
        app = await self._get_app()

        inputs = {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
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
        self,
        session_id: str,
        query: str = None,
        role: str = "user",
        resume_data: Any = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        # Compiled Graph
        app = await self._get_app()

        # Checkpointer 설정
        config = {"configurable": {"thread_id": session_id}}

        if resume_data is not None:
            inputs = Command(resume=resume_data)
            logger.info(f"Session {session_id}: Resuming with data: {resume_data}")
        else:
            # Graph 입력 값
            inputs = {
                "messages": [HumanMessage(content=query)],
                "original_query": query,
            }

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
                        session_id=session_id, node=name, message=NODE_STATUS_MAP[name]
                    )

                # Keep-alive
                elif (
                    kind == "on_chat_model_stream"
                    and event["metadata"].get("langgraph_node") == "generate_final_answer"
                ):
                    current_time = time.perf_counter()

                    # 최소 1초 간격으로 ping을 보냄
                    if current_time - last_ping_time > 1.0:
                        yield ChatStreamingKeepAliveResponse(session_id=session_id)

                        last_ping_time = current_time

                # generate node 종료 시점에 수행할 작업
                elif kind == "on_chain_end" and name in ("generate_final_answer", "chitchat"):
                    end = time.perf_counter()
                    elapsed_time = end - start

                    # 최종 상태 획득
                    node_output = event["data"].get("output")

                    if node_output:
                        last_message = node_output["messages"][-1]
                        answer_text = last_message.content  # 최종 답변
                        sources = node_output.get("sources", [])  # 출처

                        snapshot = await app.aget_state(config)
                        current_state = snapshot.values
                        related_jira_issues = current_state.get(
                            "related_jira_issues", []
                        )  # 관련 Jira 이슈

                        yield ChatStreamingFinalResponse(
                            session_id=session_id,
                            node=name,
                            answer=answer_text,
                            sources=sources,
                            related_jira_issues=related_jira_issues,
                            process_time=elapsed_time,
                        )

            snapshot = await app.aget_state(config)

            if snapshot.next and (
                (payload := snapshot.tasks[0].interrupts) is not None
            ):
                interrupt_value = payload[0].value

                logger.info(f"Session {session_id}: Interrupted at {snapshot.next}")

                yield ChatStreamingInterruptResponse(
                    session_id=session_id,
                    node=list(snapshot.next)[0],
                    payload=interrupt_value,
                )

        except asyncio.CancelledError:
            logger.warning("클라이언트 연결이 종료되었습니다.")
            raise

        except Exception as e:
            logger.error(f"Streaming 중 에러 발생: {e}")

        finally:
            elapsed_time = time.perf_counter() - start
            logger.info(f"Streaming 종료. ===> duration: {elapsed_time:.4f}s")
