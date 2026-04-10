from typing import Literal

import structlog
from langchain.chat_models import BaseChatModel

from catchup.costs.utils import extract_token_usages
from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import log_node
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def route_node(state: AgentState, llm: BaseChatModel):
    query = state["original_query"]
    global_context = state["global_context"].model_dump()
    prompt = prompt_loader.get_prompt(
        "rag/route",
        query=query,
        **global_context, 
    )
    token_usages = {"token_breakdown": {}}

    try:
        async with rag_semaphores.analysis:
            raw_response = await llm.ainvoke(input=prompt)
            token_usages = extract_token_usages(raw_response)
            content = raw_response.content
        intent = _refine_content(content)

    except Exception as e:  
        logger.warning(
            "route_node_failed",
            error=str(e),
            exc_info=True
        )
        return {
            "intent": "search_pipeline",
        }

    logger.debug(
        "intent_classified",
        intent=intent
    )

    return {
        "intent": intent,
        **token_usages,
    }


def _refine_content(answer: str) -> str:
    cleaned_answer = answer.strip().lower()
    if "chitchat" in cleaned_answer:
        intent: Literal["chitchat", "search_pipeline"] = "chitchat"
    else:
        intent: Literal["chitchat", "search_pipeline"] = "search_pipeline"
    return intent
