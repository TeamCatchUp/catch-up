import asyncio
from collections import defaultdict
import logging
import re
from typing import Annotated, Any

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from numpy import full

from app.core.config import settings
from app.observability.langfuse_client import langfuse_handler
from app.rag.factory import (
    get_github_service,
    get_llm_service,
    get_rerank_service,
    get_vector_repository
)
from app.rag.models.dto import BaseSource, JiraSource
from app.rag.models.grade import GradeDocuments
from app.rag.models.plan import SearchPlan, SearchQuery
from app.rag.models.retrieve import (
    JiraIssueSearchResult,
    SourceType,
    BaseSearchResult,
    CodeSearchResult,
    PullRequestSearchResult,
    IssueSearchResult
)
from app.rag.models.manage_pr_context import PullRequestCandidate, PullRequestUserSelected
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
    "jira_issue": ["_jira_issue"],
    "github_issue": ["_gh_issue", "_issue"],
    "pr_history": ["_pr"],
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
    
    flat_docs: list[BaseSearchResult]= []

    for docs in search_results:
        for doc in docs:
            source_type = doc.metadata.get("source_type")
            try:
                if source_type == SourceType.CODE:                   
                    flat_docs.append(CodeSearchResult.from_search_result_doc(doc))
                    
                elif source_type == SourceType.PULL_REQUEST:
                    flat_docs.append(PullRequestSearchResult.from_search_result_doc(doc))
                    
                elif source_type == SourceType.ISSUE:
                    flat_docs.append(IssueSearchResult.from_search_result_doc(doc))
                
                elif source_type == SourceType.JIRA_ISSUE:
                    flat_docs.append(JiraIssueSearchResult.from_search_result_doc(doc))
            except Exception as e:
                logger.warning(f"Failed to parse document {doc.metadata.get("id")}: {e}")            

    logger.info(
        f"총 검색된 문서 수: {len(flat_docs)} (Budget: {settings.MEILISEARCH_GLOBAL_RETRIEVAL_BUDGET})"
    )

    return {"retrieved_docs": flat_docs}


async def rerank_node(state: AgentState):
    logger.info("rerank node 진입")
    rerank_service = get_rerank_service()

    query = state.get("current_query") or state["messages"][-1].content

    retrieved_docs: list[BaseSearchResult] = state.get("retrieved_docs", [])
    
    if not retrieved_docs:
        return {"retrieved_docs": []}

    async with rerank_semaphore:
        reranked_docs = await rerank_service.rerank(
            query=query,
            documents=retrieved_docs,
            top_n=len(retrieved_docs)
        )
        
    final_docs = select_diverse_top_k(
        reranked_docs=reranked_docs,
        total_k=settings.CUSTOM_RERANK_TOTAL_K,  # 최종 10개
        min_guarantee=2  # 최소 2개 보장
    )
        
    return {"retrieved_docs": final_docs}


async def manage_pr_context_node(state: AgentState):
    logger.info("manage_pr_context node 진입")
    
    github_service = get_github_service()
    
    retrieved_docs: list[BaseSearchResult] = state.get("retrieved_docs", [])  # truth
    
    pr_docs: list[PullRequestSearchResult] = [
        doc for doc in retrieved_docs
        if doc.source_type == SourceType.PULL_REQUEST
    ]

    if not pr_docs:
        logger.info("Skip: PR 관련 문서 없음")
        return {"retrieved_docs": retrieved_docs}
    
    target_prs: list[PullRequestSearchResult] = []

    if len(pr_docs) == 1:
        logger.info(f"PR 1개 발견. 자동 선택 - [#{pr_docs[0].pr_number}]")
        target_prs = [pr_docs[0]]
    
    else:
        logger.info(f"PR {len(pr_docs)}개 발견. 사용자 선택 요청 (Interrupt)")
        
        candidates: list[dict[str, Any]] = [
            PullRequestCandidate.from_search_result_doc(doc).model_dump()
            for doc in pr_docs
        ]
                
        user_selected_prs: list[PullRequestUserSelected] = interrupt(candidates)
        logger.info(f"사용자 선택 완료: {len(user_selected_prs)} 개")
        
        if not user_selected_prs:
            logger.info("Skip: 사용자가 선택한 PR이 없음.")
            return {"retrieved_docs": retrieved_docs}
        
        selected_pr_numbers = {item.pr_number for item in user_selected_prs}
        
        target_prs: list[PullRequestSearchResult] = [
                pr for pr in pr_docs 
                if pr.pr_number in selected_pr_numbers
            ]
        
    tasks = [
        github_service.get_pr_context(pr.owner, pr.repo, pr.pr_number)
        for pr in target_prs
    ]
    
    results = await asyncio.gather(*tasks)
    
    for pr, context_data in zip(target_prs, results):
        pr.file_context = context_data
        logger.info(f"PR #{pr.pr_number} 컨텍스트 업데이트 완료 ({len(context_data)} 파일)")
    
    return {"retrieved_docs": retrieved_docs}


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

    retrieved_docs: list[BaseSearchResult] = state.get("retrieved_docs", [])

    context_text = "\n\n".join(
        [
            doc.to_context_text(index=i) 
            for i, doc in enumerate(retrieved_docs, start=1)
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
    
    forced_query = (
        f"{current_query}\n\n"
        "---"
        "**[답변 작성 시 절대 규칙]**\n"
        "1. 문장 중간이 아닌, 반드시 **문장의 맨 끝(마침표 앞)**에만 **출처 `[번호]`**를 표기하세요.\n"
        "2. 특히 Jira 이슈는 내용이 짧더라도 작업의 증거이므로 반드시 인용해야 합니다.\n"
        "3. 출처를 표기하지 않을 거면 차라리 그 문장을 쓰지 마세요."
    )

    # agent state로부터 검색 결과 획득
    retrieved_docs: list[BaseSearchResult] = state.get("retrieved_docs", [])

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
                "query": forced_query,
                "role": state.get("role", "user"),
            },
            config={"callbacks": [langfuse_handler]},
        )

    # LLM이 답변에 사용한 Document의 인덱스 파싱
    cited_indices = extract_citation(answer)
    logger.info(f"LLM이 인용한 문서 인덱스: {cited_indices}")

    # 사용자에게 제공할 최종 source 정제.
    final_sources = _select_final_sources(
        processed_sources=processed_sources,
        cited_indices=cited_indices,
        target_k=8,
        sanity_threshold=settings.FINAL_SOURCES_SANITY_THRESHOLD,
    )

    return {"messages": [AIMessage(content=answer)], "sources": final_sources}


async def search_related_jira_node(state: AgentState):
    logger.info("search_related_jira node 진입")
    
    query = state.get("current_query") or get_latest_query(state["messages"])
    
    user_index_list = state.get("index_list", [])
    
    jira_indices = [idx for idx in user_index_list if "_jira_issue" in idx]
    
    if not jira_indices:
        return {"related_jira_issues": []}
    
    meili_repo = get_vector_repository()
    
    limit = 20
    search_requests = [
        {
            "index_name": uid,
            "query": query,
            "k": limit,
            "semantic_ratio": 0.5,
        }
        for uid in jira_indices
    ]
    
    try:
        search_result_docs = await meili_repo.multi_search(search_requests)
        
        scored_issues: list[tuple[float, JiraIssueSearchResult]] = []
        
        for docs in search_result_docs:
            for doc in docs:
                try:
                    issue_model = JiraIssueSearchResult.from_search_result_doc(doc)
                    score = doc.metadata.get("_rankingScore", 0.0)
                    scored_issues.append((score, issue_model))
                except Exception as e:
                    logger.warning(f"Jira Document 파싱 실패: {e}")
        
        scored_issues.sort(key=lambda x: x[0], reverse=True)
        
        final_top_k = 10
        jira_sources: list[JiraSource] = [
            JiraSource.from_search_result(index=-1, doc=issue, is_cited=False)
            for _, issue in scored_issues[:final_top_k]
        ]
        
        logger.info(f"Jira 이슈 검색 완료: {len(jira_sources)}개")
        return {"related_jira_issues": jira_sources}
    
    except Exception as e:
        logger.error(f"Jira 노드 에러: {e}")
        return {"related_jira_issues": []}


def select_diverse_top_k(
    reranked_docs: list[BaseSearchResult],
    total_k: int,
    min_guarantee: int
) -> list[BaseSearchResult]:
    """Rerank된 소스 타입들이 골고루 섞이도록 동적으로 Top K 선정"""
    
    if not reranked_docs:
        return []
    
    # 문서 그룹핑
    docs_by_source_type: dict[SourceType, list[BaseSearchResult]] = defaultdict(list)
    for doc in reranked_docs:
        docs_by_source_type[doc.source_type].append(doc)
    
    # Source Type 종류
    active_source_types: list[SourceType] = list(docs_by_source_type.keys())
    
    selected_docs = []
    seen_ids = set()
    
    # 최소 보장 개수만큼 slot 차지
    for source_type in active_source_types:
        
        # 특정 Source Type에 해당하는 문서 후보
        candidates = docs_by_source_type[source_type]
        
        # 할당량 결정
        count_to_take = min(len(candidates), min_guarantee)
        for i in range(count_to_take):
            if len(selected_docs) >= total_k:
                break
            
            doc = candidates[i]
            if doc.id not in seen_ids:
                selected_docs.append(doc)
                seen_ids.add(doc.id)
    
    remaining_slots = total_k - len(selected_docs)
    
    # 자리가 남았으면 selected_docs에 아직 포함되지 않은 것들을 앞에서부터 넣어줌 (이미 reranker가 정렬해준 상태)
    if remaining_slots > 0:
        for doc in reranked_docs:
            if doc.id not in seen_ids:
                selected_docs.append(doc)
                seen_ids.add(doc.id)
                remaining_slots -= 1
                if remaining_slots == 0:
                    break
    
    # 고르게 담긴 문서들을 relevance_score 기준으로 정렬해서 LLM에게 제공
    selected_docs.sort(key=lambda x: x.relevance_score, reverse=True)
    
    return selected_docs
    

def _preprocess_documents(
    retrieved_docs: list[BaseSearchResult],
) -> tuple[str, list[dict[str, Any]]]:
    """
    검색 결과를 LLM용 Context Text와 Frontend용 Source 객체로 변환
    """
    # context_text 생성을 위한 임시 리스트
    context_text_list = []

    # 사용자 제공용 Source 리스트
    processed_sources = []

    for i, doc in enumerate(retrieved_docs, start=1):
        formatted_text = doc.to_context_text(index=i)
        context_text_list.append(formatted_text)
        
        source_dto = BaseSource.from_search_result(index=i, doc=doc)
        processed_sources.append(source_dto)

    # LLM 제공용 context 연결
    full_context_text = "\n\n".join(context_text_list)
    
    return full_context_text, processed_sources


def _select_final_sources(
    processed_sources: list[BaseSource], 
    cited_indices: set[int],
    target_k: int = 5,
    sanity_threshold: float = 0.01
) -> list[BaseSource]:
    """
    인용 여부, Threshold, Fallback 로직을 통해 최종 Source 리스트 선정 및 정렬
    """
    final_sources: list[BaseSource] = []
    seen_indices = set()

    # LLM이 인용한 document가 존재하는 경우
    if cited_indices:
        for cited_num in cited_indices:
            idx = cited_num - 1  # 1-based -> 0-based 변환
            if 0 <= idx < len(processed_sources):
                if idx not in seen_indices:
                    processed_sources[idx].is_cited = True
                    final_sources.append(processed_sources[idx])
                    seen_indices.add(idx)
                    
        logger.info(f"LLM이 인용한 문서: {len(final_sources)}개")

    # 점수 내림차순 정렬 (객체 자체 정렬)
    sorted_candidates = sorted(
        processed_sources, 
        key=lambda x: x.relevance_score,
        reverse=True
    )

    for doc in sorted_candidates:
        if len(final_sources) >= target_k:
            break
        
        idx = doc.index - 1
        if idx in seen_indices:
            continue
        
        if (doc.relevance_score or 0.0) < sanity_threshold:
            continue
        
        final_sources.append(doc)
        seen_indices.add(idx)
        
    logger.info(f"최종 선별된 문서 수: {len(final_sources)}개 (Target K: {target_k})")

    # 1순위: 인용 여부
    # 2순위: Relevance Score 기준 내림차순
    final_sources.sort(key=lambda x: (not x.is_cited, x.index))

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
