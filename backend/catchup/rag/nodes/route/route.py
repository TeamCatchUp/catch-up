from typing import Literal

import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import llm_semaphore
from catchup.rag.nodes.utils import log_node
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
async def route_node(state: AgentState, llm: BaseChatModel):
    query = state["original_query"]
    
    global_context = state["global_context"].model_dump()
    
    prompt = prompt_loader.get_prompt(
        "rag/route",
        query=query,
        **global_context, 
    )

    chain = llm | StrOutputParser()

    try:
        async with llm_semaphore:
            raw_response: str = await chain.ainvoke(input=prompt)
            
        intent = _refine_response(raw_response)

    except Exception as e:  
        logger.warning(
            "route_node_failed",
            error=str(e),
            exc_info=True
        )
        return {"intent": "search_pipeline"}

    logger.debug(
        "intent_classified",
        intent=intent
    )

    return {
        "intent": intent,
        "retry_count": 0,
        "grade_comment": None,
        "grade_status": None,
        "vector_search_queries": [],
        "graph_search_queries": [],
        "retrieved_docs": [],
    }


def _refine_response(response: str) -> str:
    
    cleaned_response = response.strip().lower()
    
    if "chitchat" in cleaned_response:
        intent: Literal["chitchat", "search_pipeline"] = "chitchat"
    else:
        intent: Literal["chitchat", "search_pipeline"] = "search_pipeline"
        
    return intent