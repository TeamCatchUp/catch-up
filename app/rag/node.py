from app.rag.service.llm import LlmService
from app.rag.repository.meili import LangChainMeiliRepository
from app.rag.state import AgentState
from typing import Annotated
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langgraph.graph.message import add_messages
from app.rag.models.grade import GradeDocuments
from app.rag.prompts.utils import get_prompt_template
from app.rag.prompts.system import SYSTEM_ASSISTANT_PROMPT


llm_service = LlmService()
llm = llm_service.get_llm()
trimmer = llm_service.get_trimmer()
meili_repo = LangChainMeiliRepository()

async def rewrite_node(state: AgentState):
    messages = state["messages"]
    original_question = get_latest_query(messages)
    current_try_cnt = state.get("retry_count", 0)
    
    conversation_history = []
    for m in messages[:-1][-6:]:
        if isinstance(m, HumanMessage):
            conversation_history.append(f"User: {m.content}")
        elif isinstance(m, AIMessage):
            conversation_history.append(f"Assistant: {m.content}")
            
    history_text = "\n".join(conversation_history)
    
    prompt = get_prompt_template("rewrite")
    
    chain = prompt | llm | StrOutputParser()
    response = await chain.ainvoke({
            "history": history_text,
            "question": original_question,
        })
        
    return {
            "current_query": response,
            "retry_count": current_try_cnt + 1
        }


async def retrieve_node(state: AgentState):
    query = state.get("current_query") or state["messages"][-1].content
    
    docs = meili_repo.retrieve(query=query, k=3)
    
    tool_messages = []
    for doc in docs:
        tool_messages.append(ToolMessage(
             content=doc.page_content,
             tool_call_id=f"search_{query[:5]}",
             name="meilisearch",
             artifact=doc.metadata
        ))
    
    return {"messages": tool_messages}


async def grade_node(state: AgentState):
    messages = state["messages"]
    
    # State에 저장된 current_query가 있다면 사용 (rewritten query 우선)
    question = state.get("current_query") or get_latest_query(messages)
    
    # retry는 최대 3번까지만 재시도
    if state.get("retry_count") >= 3:
        return "generate_answer"
    
    # 최근 retrieval 결과 추출
    recent_context = []
    for m in reversed(messages):
        if isinstance(m, ToolMessage):
            recent_context.append(m.content)
        elif isinstance(m, HumanMessage):
            break
    
    context = "\n".join(recent_context)
        
    prompt = get_prompt_template("grade")
    
    chain = prompt | llm.with_structured_output(GradeDocuments, method="function_calling")

    response = await chain.ainvoke({
        "question": question,
        "context": context
    })
    
    is_relevant = response.binary_score == "yes"
    
    return "generate_answer" if is_relevant else "rewrite_answer"


async def generate_node(state: AgentState):
    messages = state["messages"]
    
    current_query = state.get("current_query") or get_latest_query(messages)
    
    recent_context = []
    for m in reversed(messages):
        if isinstance(m, ToolMessage):
            recent_context.append(m.content)
        elif isinstance(m, HumanMessage):
            break
    
    context_text = "\n\n".join(recent_context)
    
    prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_ASSISTANT_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{query}")
        ])
    
    chain = prompt | llm | StrOutputParser()
    
    conversation_messages = [
        m for m in messages if isinstance(m, (HumanMessage, AIMessage))
    ]
    
    trimmed_history = trimmer.invoke(conversation_messages)
    
    answer = await chain.ainvoke({
        "history": trimmed_history,
        "context": context_text,
        "query": current_query,
        "role": state.get("role", "user")
    })
    
    return {"messages": [AIMessage(content=answer)]}


def get_latest_query(messages: Annotated[list, add_messages]):
    return next(
            (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
        )