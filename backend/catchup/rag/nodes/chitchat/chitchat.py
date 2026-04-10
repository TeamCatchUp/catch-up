import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

from catchup.costs.utils import extract_token_usages
from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.policies import FALLBACK_ANSWER
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()

@log_node
@token_usage
async def chitchat_node(state: AgentState, llm: BaseChatModel):
    query = state["original_query"]
    conversation_history = get_conversation_history(state["messages"])
    global_context = state["global_context"].model_dump()
    prompt = prompt_loader.get_prompt(
        "rag/chitchat",
        **global_context
    )
    messages = (
        [SystemMessage(content=prompt)]
        + conversation_history 
        + [HumanMessage(content=query)]
    )
    token_usages = {"token_breakdown": {}}
    
    try:
        async with rag_semaphores.analysis:
            raw_response = await llm.ainvoke(input=messages)
            token_usages = extract_token_usages(raw_response)
            chitchat = raw_response.content
            logger.debug(
                "chitchat_answer_generated",
                original_query=state.get("original_query"),
                answer=chitchat
            )

    except Exception as e:
        logger.error(
            "chitchat_node_failed",
            fallback="fallback_answer_generated",
            exc_info=True,
            error=str(e)
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
