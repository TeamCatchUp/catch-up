import asyncio
import logging
import re
from typing import Annotated, Any

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph.message import add_messages

from app.core.config import settings
from app.observability.langfuse_client import langfuse_handler
from app.rag.factory import get_llm_service, get_rerank_service, get_vector_repository
from app.rag.models.grade import GradeDocuments
from app.rag.models.plan import SearchPlan, SearchQuery
from app.rag.models.route import RouteQuery
from app.rag.prompts.system import (
    SYSTEM_ASSISTANT_PROMPT,
    SYSTEM_CHITCHAT_PROMPT,
    SYSTEM_QUERY_ROUTER_PROMPT,
)
from app.rag.prompts.utils import get_prompt_template
from app.rag.state import AgentState

logger = logging.getLogger(__name__)


# llm 호출 Rate Limit 방어
llm_semaphore = asyncio.Semaphore(10)
rerank_semaphore = asyncio.Semaphore(10)


INDEX_MAPPING_RULES = {
    "codebase": ["_code"],
    "jira_issue": ["_jira", "_ticket"],
    "github_issue": ["_gh_issue", "_issue"],
    "pr_history": ["_pr", "_commit"],
}


async def router_node(state: AgentState):
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


async def chitchat_node(state: AgentState):
    logger.info("chitchat node 진입")
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

    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={"messages": filtered_messages},
            config={"callbacks": [langfuse_handler]},
        )

    return {"messages": [AIMessage(content=answer)], "sources": []}


async def rewrite_node(state: AgentState):
    logger.info("rewrite node 진입")
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

    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={
                "history": history_text,
                "question": original_question,
            },
            config={"callbacks": [langfuse_handler]},
        )

    logger.info(f"원본 쿼리: {original_question}\n재작성된 쿼리: {answer}")

    return {"current_query": answer, "retry_count": current_try_cnt + 1}


async def plan_node(state: AgentState):
    logger.info("plan node 진입")
    llm_service = get_llm_service()
    llm = llm_service.get_llm()

    current_query = state.get("current_query") or get_latest_query(state["messages"])

    structured_llm = llm.with_structured_output(SearchPlan, method="function_calling")

    prompt = get_prompt_template("plan")

    chain = prompt | structured_llm

    async with llm_semaphore:
        plan: SearchPlan = await chain.ainvoke(
            input={"current_query": current_query},
            config={"callbacks": [langfuse_handler]},
        )

    for q in plan.queries:
        logger.info(f"query plan: [{q.datasource}] {q.query}")

    return {"search_queries": plan.queries}


async def retrieve_node(state: AgentState):
    logger.info("retrieve 노드 진입")

    meili_repo = get_vector_repository()

    plans = state.get("search_queries", [])
    user_scope = state.get("index_list", [])

    if not plans:
        logger.warning("검색 계획 없음. Fallback 실행.")
        current_query = state.get("current_query") or get_latest_query(
            state["messages"][-1].content
        )
        plans = [SearchQuery(datasource="codebase", query=current_query)]

    search_requests = []

    total_target_indicies = 0
    resolved_plans: list[tuple[str, str]] = []

    for plan in plans:
        target_indices = _resolve_indices(plan.datasource, user_scope)
        if target_indices:
            total_target_indicies += len(target_indices)
            resolved_plans.append((plan, target_indices))
        else:
            logger.info(f"Skip: {plan.datasource} (User Scope 없음)")

    if total_target_indicies == 0:
        logger.warning("실행할 검색 작업이 없습니다.")

    dynamic_k = max(
        settings.MEILISEARCH_MIN_K_PER_INDEX,
        settings.MEILISEARCH_GLOBAL_RETRIEVAL_BUDGET // total_target_indicies,
    )
    logger.info(
        f"Dynmic K 적용 중: 총 {total_target_indicies}개 인덱스 (각 {dynamic_k}개 문서 검색)"
    )

    for plan, indicies in resolved_plans:
        for index_name in indicies:
            search_requests.append(
                {
                    "index_name": index_name,
                    "query": plan.query,
                    "k": dynamic_k,
                    "semantic_ratio": settings.MEILISEARCH_SEMANTIC_RATIO,
                }
            )

    search_plan = [
        {
            "index": req["index_name"],
            "query": req["query"],
        }
        for req in search_requests
    ]
    logger.info("검색 계획: %s", search_plan)

    search_results: list[list[Document]] = await meili_repo.multi_search(
        search_requests
    )

    flat_docs = []

    for docs in search_results:
        for doc in docs:
            flat_docs.append(
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

    logger.info(
        f"총 검색된 문서 수: {len(flat_docs)} (Budget: {settings.MEILISEARCH_GLOBAL_RETRIEVAL_BUDGET})"
    )

    return {"retrieved_docs": flat_docs}


async def rerank_node(state: AgentState):
    logger.info("rerank node 진입")
    rerank_service = get_rerank_service()

    query = state.get("current_query") or state["messages"][-1].content

    retrieved_docs = state.get("retrieved_docs", [])

    async with rerank_semaphore:
        reranked_docs = await rerank_service.rerank(
            query=query, documents=retrieved_docs, top_n=settings.COHERE_RERANK_TOP_N
        )

    return {"retrieved_docs": reranked_docs}


async def grade_node(state: AgentState):
    logger.info("grade node 진입")
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

    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={"question": question, "context": context_text},
            config={"callbacks": [langfuse_handler]},
        )

    is_relevant = answer.binary_score == "yes"

    return {"grade_status": "good" if is_relevant else "bad"}


async def generate_node(state: AgentState):
    logger.info("generate node 진입")
    llm_service = get_llm_service()
    llm = llm_service.get_llm()
    trimmer = llm_service.get_trimmer()

    messages = state["messages"]
    current_query = get_latest_query(messages)

    # agent state로부터 검색 결과 획득
    retrieved_docs: list[dict[str, Any]] = state.get("retrieved_docs", [])

    # 문서 전처리 (Context 텍스트 생성 및 Source 객체 초기화)
    context_text, processed_sources = _preprocess_documents(retrieved_docs)

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

    # 마지막 대화를 제외한 모든 사용자-어시스턴트 대화 내용
    history_messages = conversation_messages[:-1]

    # 대화 히스토리 trim
    trimmed_history = trimmer.invoke(history_messages)

    # LLM 호출
    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={
                "history": trimmed_history,
                "context": context_text,
                "query": current_query,
                "role": state.get("role", "user"),
            },
            config={"callbacks": [langfuse_handler]},
        )

    # LLM이 답변에 사용한 Document의 인덱스 파싱
    cited_indices = extract_citation(answer)
    logger.info(f"LLM이 인용한 문서 인덱스: {cited_indices}")

    # 사용자에게 제공할 최종 source 정제
    final_sources = _select_final_sources(
        processed_sources=processed_sources,
        cited_indices=cited_indices,
        threshold=settings.RERANK_THRESHOLD,
    )

    return {"messages": [AIMessage(content=answer)], "sources": final_sources}


def _preprocess_documents(
    retrieved_docs: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """
    검색 결과를 LLM용 Context Text와 Frontend용 Source 객체로 변환
    """
    # context_text 생성을 위한 임시 리스트
    context_text_list = []

    # 사용자 제공용 Source 리스트
    processed_sources = []

    for i, doc in enumerate(retrieved_docs):
        # LLM 제공용 Context 상세
        source = doc.get("source", "unknown")
        category = doc.get("category", "기타")
        file_path = doc.get("file_path", "")
        text = doc.get("text", "")

        formatted_doc = (
            f"[{i}] 출처: {source} ({file_path}) | 카테고리: {category}\n내용:\n{text}"
        )
        context_text_list.append(formatted_doc)

        # 사용자에게 반환할 Source 객체 사전 생성
        source_entry = {
            "index": i,  # Rerank 결과 상의 원래 ID
            "is_cited": False,
            "source_type": "github",
            "text": text,  # 원문 전체
            "file_path": file_path,
            "category": category,
            "source": source,
            "html_url": doc.get("html_url"),
            "language": doc.get("language"),
            "relevance_score": doc.get("relevance_score"),
        }
        processed_sources.append(source_entry)

    # LLM 제공용 context 연결
    context_text = "\n\n".join(context_text_list)

    return context_text, processed_sources


def _select_final_sources(
    processed_sources: list[dict[str, Any]], cited_indices: set[int], threshold: float
) -> list[dict[str, Any]]:
    """
    인용 여부, Threshold, Fallback 로직을 통해 최종 Source 리스트 선정 및 정렬
    """
    final_sources = []
    seen_indices = set()

    # LLM이 인용한 document가 존재하는 경우
    if cited_indices:
        valid_indices = [i for i in cited_indices if 0 <= i < len(processed_sources)]
        for i in valid_indices:
            if i not in seen_indices:
                processed_sources[i]["is_cited"] = True
                final_sources.append(processed_sources[i])
                seen_indices.add(i)
        logger.info(f"LLM이 인용한 문서: {len(final_sources)}개")

    # 점수 내림차순 정렬 (객체 자체 정렬)
    sorted_by_score = sorted(
        processed_sources, key=lambda x: x["relevance_score"], reverse=True
    )

    # LLM이 언급하지 않았지만 threshold 기준으로 관련 있는 문서
    cnt = 0
    for doc in sorted_by_score:
        idx = doc["index"]
        if doc.get("relevance_score") >= threshold:
            if idx not in seen_indices:
                final_sources.append(doc)
                seen_indices.add(idx)
                cnt += 1
    logger.info(f"threshold를 통과한 문서: {cnt}개")

    # 인용도 없고 점수도 전부 낮은 경우에 top-3 (Fallback)
    if not final_sources and processed_sources:
        logger.info(
            "Fallback: 인용 또는 Threshold 기반 답변 출처가 존재하지 않습니다. Top-3개의 문서를 출처에 포함합니다."
        )
        # 이미 점수순으로 정렬된 리스트 활용
        for doc in sorted_by_score[:3]:
            idx = doc["index"]
            final_sources.append(doc)
            seen_indices.add(idx)

    # 인용된 것이 먼저 오고, 원본 인덱스 기준 오름차순 정렬
    final_sources.sort(key=lambda x: (not x["is_cited"], x["index"]))

    return final_sources


def get_latest_query(messages: Annotated[list, add_messages]):
    return next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )


def extract_citation(text: str) -> set[int]:
    matches = re.findall(r"\[(\d+(?:,\s*\d+)*)\]", text)

    indices = set()
    for match in matches:
        for num_str in match.split(","):
            if num_str.strip().isdigit():
                indices.add(int(num_str.strip()))

    return indices


def _resolve_indices(datasource_type: str, user_scope: list[str]) -> list[str]:
    valid_suffix = INDEX_MAPPING_RULES.get(datasource_type, [])
    resolved = []

    for index_name in user_scope:
        if any(suffix in index_name for suffix in valid_suffix):
            resolved.append(index_name)

    return resolved
