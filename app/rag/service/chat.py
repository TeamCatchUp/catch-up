from app.rag.graph import get_compiled_graph
from app.rag.models.dto import ChatResponse
from langchain_core.messages import HumanMessage


class ChatService:
    def __init__(self):
        pass

    async def chat(self, query: str, role: str, session_id: str) -> ChatResponse:
        app = await get_compiled_graph()

        inputs = {"messages": [HumanMessage(content=query)], "role": role}

        config = {"configurable": {"thread_id": session_id}}

        final_state = await app.ainvoke(inputs, config)

        last_message = final_state["messages"][-1]
        sources = final_state.get("sources", [])

        answer_text = (
            last_message.content
            if hasattr(last_message, "content")
            else "답변을 생성하지 못했습니다."
        )

        return ChatResponse(answer=answer_text, sources=sources)
