import asyncio
import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.callbacks import adispatch_custom_event

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import get_formatted_history_text
from catchup.rag.nodes.utils import log_node
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
    prompt = prompt_loader.get_prompt(
        "rag/rewrite",
        history=history_text,
        feedback=grade_comment,
        original_query=original_query,
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

    except asyncio.TimeoutError as e:
        raise e
    except Exception:
        await adispatch_custom_event(
            "process",
            {
                "status": "completed",  # Fallback이므로 error 처리하지 않음.
                "node": "rewrite",
                "content": original_query,
            },
        )
        return {
            "rewritten_query": original_query,
        }

    logger.debug(
        "query_rewrite_result",
        original_query=original_query,
        feedback=grade_comment,
        rewritten_query=rewritten_query,
    )
    
    await adispatch_custom_event(
            "process",
            {
                "status": "completed",
                "node": "rewrite",
                "content": rewritten_query,
            },
        )

    return {"rewritten_query": rewritten_query, **token_usages}
