import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from catchup.components.llm.service import LlmProvider
from catchup.components.llm.factory import get_llm_service
from catchup.observability.langfuse_client import langfuse_handler
from catchup.rag.nodes.chitchat.prompt import CHITCHAT_PROMPT
from catchup.rag.nodes.utils import llm_semaphore
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


async def chitchat_node(state: AgentState):
    logger.info("chitchat node 진입")
    llm_service = get_llm_service(LlmProvider.OPENAI)
    llm = llm_service.get_llm()

    messages = state["messages"]

    filtered_messages = [
        m for m in messages if isinstance(m, (HumanMessage, AIMessage))
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CHITCHAT_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    chain = prompt | llm | StrOutputParser()

    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={"messages": filtered_messages},
            config={"callbacks": [langfuse_handler]},
        )

    return {"messages": [AIMessage(content=answer)], "sources": []}
