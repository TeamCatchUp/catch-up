import structlog
from langchain.chat_models import BaseChatModel

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import get_formatted_history_text
from catchup.rag.nodes.utils import log_node
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def rewrite_node(
    state: AgentState,
    llm: BaseChatModel,
    timeout: float | None = None,
):
    conversation_history = get_conversation_history(state["messages"])
    history_text = get_formatted_history_text(conversation_history)
    original_query = state["original_query"]
    grade_comment = state.get("grade_comment", "")
    global_context = state["global_context"].model_dump()
    slack_thread_context = state.get("slack_thread_context")
    prompt = prompt_loader.get_prompt(
        "rag/rewrite",
        history=history_text,
        feedback=grade_comment,
        original_query=original_query,
        slack_thread_context=slack_thread_context,
        **global_context,
    )

    try:
        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=llm,
            messages=prompt,
            semaphore=rag_semaphores.llm_small,
            timeout=timeout,
        )
        rewritten_query = response.content

    except RETRYABLE_ERRORS as e:
        raise e
    except Exception:
        return {"rewritten_query": original_query}

    logger.debug(
        "query_rewrite_result",
        original_query=original_query,
        feedback=grade_comment,
        rewritten_query=rewritten_query,
    )

    return {"rewritten_query": rewritten_query, **token_usages}
