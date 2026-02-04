import logging

from langchain_core.documents import Document

from catchup.components.vector_db.meilisearch.factory import get_vector_repository
from catchup.configs.config import settings
from catchup.rag.nodes.utils import get_latest_query
from catchup.rag.schemas import SearchQuery
from catchup.rag.state import AgentState
from catchup.search.schemas import (
    BaseSearchResult,
    CodeSearchResult,
    IssueSearchResult,
    JiraIssueSearchResult,
    PullRequestSearchResult,
    SourceType,
)

logger = logging.getLogger(__name__)

INDEX_MAPPING_RULES = {
    "codebase": ["_code"],
    "jira_issue": ["_jira_issue"],
    "github_issue": ["_gh_issue", "_issue"],
    "pr_history": ["_pr"],
}


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

    flat_docs: list[BaseSearchResult] = []

    for docs in search_results:
        for doc in docs:
            source_type = doc.metadata.get("source_type")
            try:
                if source_type == SourceType.CODE:
                    flat_docs.append(CodeSearchResult.from_search_result_doc(doc))

                elif source_type == SourceType.PULL_REQUEST:
                    flat_docs.append(
                        PullRequestSearchResult.from_search_result_doc(doc)
                    )

                elif source_type == SourceType.ISSUE:
                    flat_docs.append(IssueSearchResult.from_search_result_doc(doc))

                elif source_type == SourceType.JIRA_ISSUE:
                    flat_docs.append(JiraIssueSearchResult.from_search_result_doc(doc))
            except Exception as e:
                logger.warning(
                    f"Failed to parse document {doc.metadata.get('id')}: {e}"
                )

    logger.info(
        f"총 검색된 문서 수: {len(flat_docs)} (Budget: {settings.MEILISEARCH_GLOBAL_RETRIEVAL_BUDGET})"
    )

    return {"retrieved_docs": flat_docs}


def _resolve_indices(datasource_type: str, user_scope: list[str]) -> list[str]:
    valid_suffix = INDEX_MAPPING_RULES.get(datasource_type, [])
    resolved = []

    for index_name in user_scope:
        if any(suffix in index_name for suffix in valid_suffix):
            resolved.append(index_name)

    return resolved
