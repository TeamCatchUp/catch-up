import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from catchup.components.llm.factory import get_llm_service
from catchup.observability.langfuse_client import langfuse_handler
from catchup.rag.nodes.rewrite.prompt import REWRITE_PROMPT
from catchup.rag.nodes.utils import get_latest_query, llm_semaphore
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


async def rewrite_node(state: AgentState):
    logger.info("rewrite node 진입")
    llm_service = get_llm_service()
    llm = llm_service.get_llm()

    messages = state["messages"]
    original_question = get_latest_query(messages)
    current_try_cnt = state.get("retry_count", 0)

    conversation_history = []
    for m in messages[:-1][-6:]:
        if isinstance(m, HumanMessage):
            conversation_history.append(f"User: {m.content}")
        elif isinstance(m, AIMessage):
            conversation_history.append(f"Assistant: {m.content}")

    history_text = "\n".join(conversation_history)

    prompt = ChatPromptTemplate.from_template(REWRITE_PROMPT)

    chain = prompt | llm | StrOutputParser()

    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={
                "history": history_text,
                "question": original_question,
            },
            config={"callbacks": [langfuse_handler]},
        )

    logger.info(f"원본 쿼리: {original_question}\n재작성된 쿼리: {answer}")

    return {"current_query": answer, "retry_count": current_try_cnt + 1}
