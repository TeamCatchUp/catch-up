import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from catchup.components.llm.factory import get_llm_service
from catchup.observability.langfuse_client import langfuse_handler
from catchup.rag.nodes.route.prompt import SYSTEM_QUERY_ROUTER_PROMPT
from catchup.rag.nodes.utils import get_latest_query, llm_semaphore
from catchup.rag.schemas import RouteQuery
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


async def route_node(state: AgentState):
    logger.info("router node 진입")
    messages = state["messages"]
    question = get_latest_query(messages)  # 반드시 가장 최근의 질문을 기반으로 답변

    logger.info(f"질문: {question}")

    llm_service = get_llm_service()
    llm = llm_service.get_llm()

    structured_llm = llm.with_structured_output(RouteQuery, method="function_calling")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_QUERY_ROUTER_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ]
    )

    filtered_messages = [
        m for m in messages if isinstance(m, (HumanMessage, AIMessage))
    ]

    history_messages = filtered_messages[:-1][-6:]

    chain = prompt | structured_llm

    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={"question": question, "history": history_messages},
            config={"callbacks": [langfuse_handler]},
        )

    return {"datasource": answer.datasource}
