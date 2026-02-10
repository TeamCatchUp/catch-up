import datetime
import logging
from typing import Literal
from langchain.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import BaseChatPromptTemplate, ChatPromptTemplate, MessagesPlaceholder

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import get_conversation_history, llm_semaphore, log_node
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def route_node(state: AgentState):
    query = state["original_query"]

    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    
    global_context = state["global_context"].model_dump()
    
    prompt = prompt_loader.get_prompt(
        node_name="route",
        query=query,
        **global_context, 
    )

    chain = llm | StrOutputParser()

    try:
        async with llm_semaphore:
            raw_response: str = await chain.ainvoke(
                input=[HumanMessage(content=prompt)]
            )
            
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