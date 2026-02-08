import logging
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.nodes.route.prompt import SYSTEM_QUERY_ROUTER_PROMPT
from catchup.rag.nodes.utils import get_conversation_history, llm_semaphore, log_node
from catchup.rag.schemas import RouteQuery
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def route_node(state: AgentState):
    query = state["original_query"]

    conversation_history = get_conversation_history(state["messages"])

    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    structured_llm = llm.with_structured_output(RouteQuery, method="function_calling")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_QUERY_ROUTER_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{query}"),
        ]
    )

    chain = prompt | structured_llm

    try:
        async with llm_semaphore:
            answer: RouteQuery = await chain.ainvoke(
                input={"query": query, "history": conversation_history}
            )

    except Exception as e:
        logger.warning(f"Router node failed: {e}")
        return {"intent": "search_pipeline"}

    logger.info(f"intent: {answer.intent}")

    return {
        "intent": answer.intent,
        "retry_count": 0,
        "grade_comment": None,
        "grade_status": None,
        "vector_search_queries": [],
        "graph_search_queries": [],
        "retrieved_docs": [],
    }
