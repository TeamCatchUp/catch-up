import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser

from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import llm_semaphore
from catchup.rag.nodes.utils import log_node
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
async def rewrite_node(state: AgentState, llm: BaseChatModel):
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
    
    chain = llm | StrOutputParser()

    try:
        async with llm_semaphore:
            answer = await chain.ainvoke(input=prompt)

    except Exception as e:
        logger.warning(
            "rewrite_node_failed",
            error=str(e),
            exc_info=True
        )
        return {"rewritten_query": original_query}

    logger.debug(
        "query_rewrite_result",
        original_query=original_query,
        feedback=grade_comment,
        rewritten_query=answer
    )

    return {"rewritten_query": answer}


def get_formatted_history_text(
    conversation_history: list[HumanMessage | AIMessage],
) -> str:
    return "\n".join([f"{msg.type}: {msg.content}" for msg in conversation_history])
