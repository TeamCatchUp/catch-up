import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.policies import FALLBACK_ANSWER
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import get_conversation_history, llm_semaphore, log_node
from catchup.rag.state import AgentState


logger = logging.getLogger(__name__)

@log_node
async def chitchat_node(state: AgentState):
    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    
    query = state["original_query"]

    conversation_history = get_conversation_history(state["messages"])
    
    global_context = state["global_context"].model_dump()

    prompt = prompt_loader.get_prompt(
        "rag/chitchat",
        **global_context
    )
    
    logger.info(conversation_history)
    
    messages = [SystemMessage(content=prompt)] + conversation_history + [HumanMessage(content=query)]

    chain = llm | StrOutputParser()

    try:
        async with llm_semaphore:
            answer = await chain.ainvoke(input=messages)
            logger.info(f"최종 답변: {answer}")

    except Exception as e:
        logger.error(f"Chitchat node failed: {e}", exc_info=True)
        return {"messages": [AIMessage(content=FALLBACK_ANSWER)], "sources": []}

    return {"messages": [AIMessage(content=answer)], "sources": []}
