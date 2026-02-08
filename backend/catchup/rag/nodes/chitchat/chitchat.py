import logging

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.nodes.chitchat.prompt import CHITCHAT_PROMPT
from catchup.rag.nodes.utils import filter_conversation, llm_semaphore, log_node
from catchup.rag.state import AgentState


logger = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "죄송합니다. 잠시 대화 연결이 원활하지 않습니다. 잠시 후 다시 시도해 주세요."
)


@log_node
async def chitchat_node(state: AgentState):
    llm = get_llm_service(LlmProvider.OPENAI).get_llm()

    filtered_messages = filter_conversation(state["messages"])

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CHITCHAT_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    chain = prompt | llm | StrOutputParser()

    try:
        async with llm_semaphore:
            answer = await chain.ainvoke(
                input={"messages": filtered_messages}
            )

    except Exception as e:
        logger.error(f"Chitchat node failed: {e}", exc_info=True)
        return {"messages": [AIMessage(content=FALLBACK_ANSWER)], "sources": []}

    return {"messages": [AIMessage(content=answer)], "sources": []}
