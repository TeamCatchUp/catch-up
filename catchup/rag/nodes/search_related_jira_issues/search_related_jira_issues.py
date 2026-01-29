import logging

from catchup.components.vector_db.meilisearch.factory import get_vector_repository
from catchup.rag.nodes.utils import get_latest_query
from catchup.rag.schemas import JiraSource
from catchup.rag.state import AgentState
from catchup.search.schemas import JiraIssueSearchResult

logger = logging.getLogger(__name__)


async def search_related_jira_issues_node(state: AgentState):
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
