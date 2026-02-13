import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import (
    get_conversation_history,
    llm_semaphore,
    log_node,
)
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def rewrite_node(state: AgentState):
    conversation_history = get_conversation_history(state["messages"])
    history_text = get_formatted_history_text(conversation_history)
    
    original_query = state["original_query"]
    
    grade_comment = state.get("grade_comment", "")
    
    global_context = state["global_context"].model_dump()
    
    prompt = prompt_loader.get_prompt(
        "rag/rewrite",
        history=history_text,
        feedback=grade_comment,
        original_query=original_query,
        **global_context
    )
    
    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    chain = llm | StrOutputParser()

    try:
        async with llm_semaphore:
            answer = await chain.ainvoke(input=prompt)

    except Exception as e:
        logger.warning(f"Rewrite node failed: {e}")
        return {"rewritten_query": original_query}

    logger.info(
        f"\n[Rewrite Result]"
        f"\n1. 원본 쿼리: {original_query}"
        f"\n2. 피드백: {grade_comment}"
        f"\n3. 재작성: {answer}"
    )

    return {"rewritten_query": answer}


def get_formatted_history_text(
    conversation_history: list[HumanMessage | AIMessage],
) -> str:
    return "\n".join([f"{msg.type}: {msg.content}" for msg in conversation_history])
