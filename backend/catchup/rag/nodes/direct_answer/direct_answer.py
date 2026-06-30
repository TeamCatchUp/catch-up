from typing import Any

import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from catchup.costs.utils import token_usage
from catchup.langgraph.retry import RETRYABLE_ERRORS
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.policies import FALLBACK_ANSWER
from catchup.rag.state import AgentState
from catchup.schemas.sources import SOURCE_METADATA
from catchup.utils.semaphores import service_semaphores

logger = structlog.get_logger()


@log_node
@token_usage
async def direct_answer_node(
    state: AgentState,
    llm: BaseChatModel,
    timeout: float | None = None,
):
    query = state["original_query"]
    conversation_history = get_conversation_history(state["messages"])
    global_context = state["global_context"].model_dump()

    prompt_settings = state.get("prompt_settings")
    slack_thread_context = state.get("slack_thread_context")
    prompts = _load_prompts(
        global_context=global_context,
        prompt_settings=prompt_settings,
        slack_thread_context=slack_thread_context,
    )
    system_message = build_system_message(
        static_prompt=prompts["system"],
        dynamic_prompts=[
            p
            for p in [
                prompts["job_role"],
                prompts["custom"],
            ]
            if p is not None
        ],
        cache_prompt=False,
    )
    messages = [system_message] + conversation_history + [HumanMessage(content=query)]

    try:
        raw_response, token_usages = await ainvoke_llm_with_token_usage(
            llm=llm,
            messages=messages,
            semaphore=service_semaphores.llm_small,
            timeout=timeout,
        )
        logger.debug(
            "direct_answer_generated",
            original_query=state.get("original_query"),
            answer=raw_response.content,
        )

    except RETRYABLE_ERRORS as e:
        raise e
    except Exception as e:
        logger.error(
            "direct_answer_node_failed",
            fallback="fallback_answer_generated",
            exc_info=True,
            error=str(e),
        )
        return {
            "messages": [AIMessage(content=FALLBACK_ANSWER)],
            "sources": [],
        }

    return {
        "messages": [raw_response],
        "sources": [],
        **token_usages,
    }


def _load_prompts(
    global_context: dict,
    prompt_settings: Any,
    slack_thread_context: str | None = None,
) -> dict:
    return {
        "system": prompt_loader.get_prompt(
            "rag/direct_answer",
            sources=list(SOURCE_METADATA.values()),
            slack_thread_context=slack_thread_context,
            **global_context,
        ),
        "job_role": prompt_loader.get_prompt(
            "settings/job_role",
            prompt_settings=prompt_settings,
        ),
        "custom": prompt_loader.get_prompt(
            "settings/custom_prompt",
            prompt_settings=prompt_settings,
        )
        if prompt_settings and prompt_settings.custom_prompt
        else None,
    }
