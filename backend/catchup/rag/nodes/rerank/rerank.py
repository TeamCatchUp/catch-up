import logging
from collections import defaultdict

from langchain_core.documents import Document

from catchup.components.reranker.service import BaseRerankService
from catchup.configs.config import settings
from catchup.rag.nodes.utils import log_node
from catchup.rag.nodes.utils import rerank_semaphore
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def rerank_node(state: AgentState, rerank_service: BaseRerankService):

    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    if not retrieved_docs:
        logger.warning("검색된 문서가 없습니다.")
        return {"retrieved_docs": []}

    query = state["rewritten_query"]

    try:
        async with rerank_semaphore:
            reranked_docs = await rerank_service.rerank(
                query=query,
                documents=retrieved_docs,
                top_n=settings.RERANK_TOP_N
            )

        final_docs = select_diverse_top_k(
            reranked_docs=reranked_docs,
            total_k=settings.RERANK_TOTAL_K,  # LLM에게 최종적으로 제공되는 문서 개수
            min_guarantee=2,  # 최소 2개 보장
        )

    except Exception as e:
        logger.warning(f"Rerank node failed: {e}", exc_info=True)
        final_docs = retrieved_docs

    return {"retrieved_docs": final_docs}


def select_diverse_top_k(
    reranked_docs: list[Document], total_k: int, min_guarantee: int
) -> list[Document]:
    """Rerank된 소스 타입들이 골고루 섞이도록 동적으로 Top K 선정"""

    if not reranked_docs:
        return []

    # 문서 그룹핑
    docs_by_source_type: dict[str, list[Document]] = defaultdict(list)
    for doc in reranked_docs:
        source_type = doc.metadata.get("source", "unknown")
        docs_by_source_type[source_type].append(doc)

    # Source Type 종류
    active_sources = list(docs_by_source_type.keys())

    selected_docs = []
    seen_ids = set()

    # 최소 보장 개수만큼 slot 차지
    for source in active_sources:
        # 특정 Source Type에 해당하는 문서 후보
        candidates = docs_by_source_type[source]

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
    selected_docs.sort(
        key=lambda x: x.metadata.get("relevance_score", 0.0), reverse=True
    )

    return selected_docs
