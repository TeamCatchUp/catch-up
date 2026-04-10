import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from catchup.costs.utils import extract_token_usages
from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def rewrite_node(state: AgentState, llm: BaseChatModel):
    conversation_history = get_conversation_history(state["messages"])
    history_text = _get_formatted_history_text(conversation_history)
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
    token_usages = {"token_breakdown": {}}

    try:
        async with rag_semaphores.analysis:
            raw_response = await llm.ainvoke(input=prompt)
            token_usages = extract_token_usages(raw_response)
            rewritten_query = raw_response.content

    except Exception as e:
        logger.warning(
            "rewrite_node_failed",
            fallback="original_query",
            error=str(e),
            exc_info=True
        )
        return {
            "rewritten_query": original_query,
        }

    logger.debug(
        "query_rewrite_result",
        original_query=original_query,
        feedback=grade_comment,
        rewritten_query=rewritten_query
    )

    return {
        "rewritten_query": rewritten_query,
        **token_usages
    }


def _get_formatted_history_text(
    conversation_history: list[HumanMessage | AIMessage],
) -> str:
    return "\n".join([f"{msg.type}: {msg.content}" for msg in conversation_history])
