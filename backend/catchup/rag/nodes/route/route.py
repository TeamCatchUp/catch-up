import logging
from typing import Literal
from langchain.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import llm_semaphore, log_node
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


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
        logger.warning(f"Router node failed: {e}")
        return {"intent": "search_pipeline"}

    logger.info(f"intent: {intent}")

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