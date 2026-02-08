import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.nodes.rewrite.prompt import REWRITE_PROMPT
from catchup.rag.nodes.utils import (
    get_conversation_history,
    llm_semaphore,
    log_node,
)
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def rewrite_node(state: AgentState):
    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    prompt = ChatPromptTemplate.from_template(REWRITE_PROMPT)
    chain = prompt | llm | StrOutputParser()

    original_query = state["original_query"]

    conversation_history = get_conversation_history(state["messages"])
    history_text = get_formatted_history_text(conversation_history)

    grade_comment = state.get("grade_comment", "")

    current_try_cnt = state.get("retry_count", 0)

    try:
        async with llm_semaphore:
            answer = await chain.ainvoke(
                input={
                    "history": history_text,
                    "original_query": original_query,
                    "feedback": grade_comment if grade_comment else "None",
                }
            )

    except Exception as e:
        logger.warning(f"Rewrite node failed: {e}")
        return {"rewritten_query": original_query, "retry_count": current_try_cnt + 1}

    logger.info(
        f"\n[Rewrite Result]"
        f"\n1. 원본 쿼리: {original_query}"
        f"\n2. 피드백: {grade_comment}"
        f"\n3. 재작성: {answer}"
    )

    return {"rewritten_query": answer, "retry_count": current_try_cnt + 1}


def get_formatted_history_text(
    conversation_history: list[HumanMessage | AIMessage],
) -> str:
    return "\n".join([f"{msg.type}: {msg.content}" for msg in conversation_history])
