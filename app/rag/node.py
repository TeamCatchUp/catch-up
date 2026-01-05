from typing import Annotated, Any
import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph.message import add_messages

from app.observability.langfuse_client import langfuse_handler
from app.rag.factory import get_llm_service, get_vector_repository, get_rerank_service
from app.rag.models.grade import GradeDocuments
from app.rag.models.route import RouteQuery
from app.rag.prompts.system import (
    SYSTEM_ASSISTANT_PROMPT,
    SYSTEM_CHITCHAT_PROMPT,
    SYSTEM_QUERY_ROUTER_PROMPT,
)
from app.rag.prompts.utils import get_prompt_template
from app.rag.state import AgentState


logger = logging.getLogger(__name__)


async def router_node(state: AgentState):
    messages = state["messages"]
    question = get_latest_query(messages) # 반드시 가장 최근의 질문을 기반으로 답변
    
    logger.info(question)
    
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
    answer = await chain.ainvoke(
        input={"question": question, "history": history_messages},
        config={"callbacks": [langfuse_handler]},
    )

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
    answer = await chain.ainvoke(
        input={"messages": filtered_messages}, config={"callbacks": [langfuse_handler]}
    )

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

    query = state.get("current_query") or state["messages"][-1].content

    target_index = state.get("index_name", "")

    docs = meili_repo.retrieve(
            query=query, 
            index_name=target_index, 
            k=100,
            semantic_ratio=0.8
        )

    doc_data_list = []
    for doc in docs:
        doc_data_list.append(
            {
                "source_type": "github",
                "text": doc.page_content,
                "file_path": doc.metadata.get("file_path"),
                "category": doc.metadata.get("category"),
                "source": doc.metadata.get("source"),
                "html_url": doc.metadata.get("html_url"),
                "language": doc.metadata.get("language"),
            }
        )

    return {"retrieved_docs": doc_data_list}


async def rerank_node(state: AgentState):
    rerank_service = get_rerank_service()
    
    query = state.get("current_query") or state["messages"][-1].content
    
    retrieved_docs = state.get("retrieved_docs", [])
    
    reranked_docs = await rerank_service.rerank(
        query=query,
        documents=retrieved_docs,
        top_n=5
    )
    
    return {"retrieved_docs": reranked_docs}


async def grade_node(state: AgentState):
    llm_service = get_llm_service()
    llm = llm_service.get_llm()

    messages = state["messages"]

    # State에 저장된 current_query가 있다면 사용 (rewritten query 우선)
    question = state.get("current_query") or get_latest_query(messages)

    # retry는 최대 3번까지만 재시도
    if state.get("retry_count", 0) >= 3:
        return {"grade_status": "max_retries"}

    retrieved_docs = state.get("retrieved_docs", [])

    context_text = "\n\n".join(
        [
            f"""
            [문서 정보]
            출처: {doc.get("source", "unknown")}
            파일 경로: {doc.get("file_path", "N/A")}
            카테고리: {doc.get("category", "N/A")}
            프로그래밍 언어: {doc.get("language", "N/A")}
            내용:
            {doc.get("text", "")}
            """.strip()
            for doc in retrieved_docs
        ]
    )

    if not context_text:
        return {"grade_status": "bad"}

    prompt = get_prompt_template("grade")

    chain = prompt | llm.with_structured_output(
        GradeDocuments, method="function_calling"
    )

    answer = await chain.ainvoke(
        input={
                "question": question,
                "context": context_text
            },
        config={"callbacks": [langfuse_handler]},
    )

    is_relevant = answer.binary_score == "yes"

    return {"grade_status": "good" if is_relevant else "bad"}


async def generate_node(state: AgentState):
    llm_service = get_llm_service()
    llm = llm_service.get_llm()
    trimmer = llm_service.get_trimmer()

    messages = state["messages"]
    current_query = get_latest_query(messages)

    # agent state로부터 검색 결과 획득
    retrieved_docs: list[dict[str, Any]] = state.get("retrieved_docs", [])

    # 검색 결과 formatting
    context_text_list = []
    for i, doc in enumerate(retrieved_docs):
        print(i, doc)
        source = doc.get("source", "unknown")
        category = doc.get("category", "기타")
        file_path = doc.get("file_path", "")
        text = doc.get("text", "")

        formatted_doc = f"[{i}] 출처: {source} ({file_path}) | 카테고리: {category}\n내용:\n{text}"
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

    history_messages = conversation_messages[:-1]
    
    # 대화 히스토리 trim
    trimmed_history = trimmer.invoke(history_messages)
    
    logger.info(context_text)

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
                "source_type": "github",
                "text": doc.get("text"), # 원문 전체
                "file_path": file_path,
                "category": doc.get("category"),
                "source": source_name,
                "html_url": doc.get("html_url"),
                "language": doc.get("language"),
            }
            unique_sources.append(source_entry)

    return {"messages": [AIMessage(content=answer)], "sources": unique_sources}


def get_latest_query(messages: Annotated[list, add_messages]):
    return next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )
