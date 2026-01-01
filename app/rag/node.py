from typing import Annotated, Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph.message import add_messages

from app.core.config import settings
from app.observability.langfuse_client import langfuse_handler
from app.rag.factory import get_llm_service, get_vector_repository
from app.rag.models.grade import GradeDocuments
from app.rag.models.route import RouteQuery
from app.rag.prompts.system import (
    SYSTEM_ASSISTANT_PROMPT,
    SYSTEM_CHITCHAT_PROMPT,
    SYSTEM_QUERY_ROUTER_PROMPT,
)
from app.rag.prompts.utils import get_prompt_template
from app.rag.state import AgentState


async def router_node(state: AgentState):
    messages = state["messages"]
    question = state.get("current_query") or get_latest_query(messages)

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
    answer = await chain.ainvoke({"question": question, "history": history_messages})

    return {"datasource": answer.datasource}


async def chitchat_node(state: AgentState):
    llm_service = get_llm_service()
    llm = llm_service.get_llm()

    messages = state["messages"]

    filtered_messages = [
        m for m in messages if isinstance(m, (HumanMessage, AIMessage))
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_CHITCHAT_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    chain = prompt | llm | StrOutputParser()
    answer = await chain.ainvoke({"messages": filtered_messages})

    return {"messages": [AIMessage(content=answer)], "sources": []}


async def rewrite_node(state: AgentState):
    llm_service = get_llm_service()
    llm = llm_service.get_llm()

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
    answer = await chain.ainvoke(
        input={
            "history": history_text,
            "question": original_question,
        },
        config={"callbacks": [langfuse_handler]},
    )

    return {"current_query": answer, "retry_count": current_try_cnt + 1}


async def retrieve_node(state: AgentState):
    meili_repo = get_vector_repository()

    datasource = state.get("datasource", "codebase")

    query = state.get("current_query") or state["messages"][-1].content

    index_map = {
        "codebase": settings.MEILI_GITHUB_CODEBASE_INDEX,
        "issue_tracker": settings.MEILI_GITHUB_ISSUES_INDEX,
        "pr_history": settings.MEILI_GITHUB_PRS_INDEX,
    }

    target_index = index_map.get(datasource, settings.MEILI_DEFAULT_INDEX)

    docs = meili_repo.retrieve(query=query, index_name=target_index, k=3)

    doc_data_list = []
    for doc in docs:
        doc_data_list.append(
            {
                "content": doc.page_content,
                "file_name": doc.metadata.get("file_name"),
                "file_path": doc.metadata.get("file_path"),
                "category": doc.metadata.get("category"),
                "source": doc.metadata.get("source"),
                "source_type": datasource,
            }
        )

    return {"retrieved_docs": doc_data_list}


async def grade_node(state: AgentState):
    llm_service = get_llm_service()
    llm = llm_service.get_llm()

    messages = state["messages"]

    # State에 저장된 current_query가 있다면 사용 (rewritten query 우선)
    question = state.get("current_query") or get_latest_query(messages)

    # retry는 최대 3번까지만 재시도
    if state.get("retry_count", 0) >= 3:
        return "generate_answer"

    retrieved_docs = state.get("retrieved_docs", [])

    context_text = "\n".join(
        [
            f"""
            파일명: {doc["file_name"]}
            경로: {doc["file_path"]}
            카테고리: {doc["category"]}
            내용:
            {doc["content"]}
            """.strip()
            for doc in retrieved_docs
        ]
    )

    if not context_text:
        return "rewrite_answer"

    prompt = get_prompt_template("grade")

    chain = prompt | llm.with_structured_output(
        GradeDocuments, method="function_calling"
    )

    answer = await chain.ainvoke(
        input={"question": question, "context": context_text},
        config={"callbacks": [langfuse_handler]},
    )

    is_relevant = answer.binary_score == "yes"

    return "generate_answer" if is_relevant else "rewrite_answer"


async def generate_node(state: AgentState):
    llm_service = get_llm_service()
    llm = llm_service.get_llm()
    trimmer = llm_service.get_trimmer()

    messages = state["messages"]
    current_query = state.get("current_query") or get_latest_query(messages)

    # agent state로부터 검색 결과 획득
    retrieved_docs: list[dict[str, Any]] = state.get("retrieved_docs", [])

    # 검색 결과 formatting
    context_text_list = []
    for i, doc in enumerate(retrieved_docs):
        print(i, doc)
        source = doc.get("source", "unknown")
        category = doc.get("category", "기타")
        file_path = doc.get("file_path", "")
        content = doc.get("content", "")

        formatted_doc = f"[{i}] 출처: {source} ({file_path}) | 카테고리: {category}\n내용:\n{content}"
        context_text_list.append(formatted_doc)
    context_text = "\n\n".join(context_text_list)

    # 프롬프트 생성
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_ASSISTANT_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{query}"),
        ]
    )

    # 체인
    chain = prompt | llm | StrOutputParser()

    # 사용자-어시스턴트 대화 필터링
    conversation_messages = [
        m for m in messages if isinstance(m, (HumanMessage, AIMessage))
    ]

    # 대화 히스토리 trim
    trimmed_history = trimmer.invoke(conversation_messages)

    # llm 호출
    answer = await chain.ainvoke(
        input={
            "history": trimmed_history,
            "context": context_text,
            "query": current_query,
            "role": state.get("role", "user"),
        },
        config={"callbacks": [langfuse_handler]},
    )

    # 사용자에게 제공할 source 정제
    unique_sources = []
    seen = set()
    for doc in retrieved_docs:
        source_name = doc.get("source", "unknown")
        file_path = doc.get("file_path", "")

        identifier = f"{source_name}_{file_path}"

        if identifier not in seen:
            seen.add(identifier)

            source_entry = {
                "source": doc.get("source", "unknown"),
                "category": doc.get("category", "기타"),
                "file_path": doc.get("file_path", ""),
                "file_name": doc.get("file_name", ""),
                "content": (doc.get("content") or "")[:500] + " ... (생략됨)",
            }

            unique_sources.append(source_entry)

    return {"messages": [AIMessage(content=answer)], "sources": unique_sources}


def get_latest_query(messages: Annotated[list, add_messages]):
    return next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )
