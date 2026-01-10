import time
from langfuse import observe
from langchain_core.messages import HumanMessage

from app.rag.graph import get_compiled_graph
from app.rag.models.dto import ChatResponse


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
    async def chat(self, query: str, role: str, session_id: str, index_name: str) -> ChatResponse:
        app = await self._get_app()

        inputs = {
                "messages": [HumanMessage(content=query)],
                "role": role,
                "index_name": index_name
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

        return ChatResponse(answer=answer_text, sources=sources, process_time=elapsed_time)
