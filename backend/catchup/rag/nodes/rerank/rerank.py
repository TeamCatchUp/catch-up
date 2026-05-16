import math
import time
from collections import Counter
from collections import defaultdict
from copy import deepcopy

import structlog
from langchain_core.documents import Document

from catchup.components.reranker.service import BaseRerankService
from catchup.configs.config import settings
from catchup.rag.nodes.utils import build_doc_groups
from catchup.rag.nodes.utils import get_document_id
from catchup.rag.nodes.utils import log_node
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()

MAX_RERANK_DOCUMENT_TEXT_LENGTH = 30_000


@log_node
async def rerank_node(state: AgentState, rerank_service: BaseRerankService):

    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    if not retrieved_docs:
        logger.warning("no_documents_retrieved")
        return {
            "retrieved_docs": [],
            "rerank_count": 0,
        }

    rerank_count: int = state.get("rerank_count", 0)
    query = state["rewritten_query"]
    
    # 실제 실행 중인 파이프라인 타입을 기준으로 K를 선정한다 (max_pipeline_type은 상한선으로 활용한다).
    pipeline_plan = state.get("pipeline_plan")
    if pipeline_plan and hasattr(pipeline_plan, "pipeline_type"):
        pipeline_type = pipeline_plan.pipeline_type
    else:
        pipeline_type = state.get("max_pipeline_type", "standard")
        
    total_k = _resolve_total_k(pipeline_type)
    
    essential_doc_ids = set(state.get("essential_doc_ids") or [])

    retrieved_docs = _validate_retrieved_docs(retrieved_docs)

    try:
        t_sem = time.perf_counter()
        logger.debug(
            "semaphore_acquiring", 
            semaphore="reranker", 
            doc_count=len(retrieved_docs),
            pipeline_type=pipeline_type,
            target_k=total_k
        )
        async with rag_semaphores.reranker:
            t_rerank = time.perf_counter()
            logger.debug(
                "rerank_invoke_start",
                semaphore_wait_elapsed=round(t_rerank - t_sem, 3),
                doc_count=len(retrieved_docs),
            )

            # Reranker에게는 충분한 후보를 전달하되, 최종 결과는 total_k로 제한한다.
            reranked_docs = await rerank_service.rerank(
                query=query, 
                documents=retrieved_docs, 
                top_n=max(total_k, settings.RERANK_TOP_N)
            )

            logger.debug(
                "rerank_invoke_completed",
                elapsed=round(time.perf_counter() - t_rerank, 3),
            )
    except RETRYABLE_ERRORS:
        raise
    except Exception as e:
        logger.warning(
            "rerank_node_failed",
            fallback="essential_prioritized_slice",
            error=str(e),
            exc_info=True,
        )
        # Rerank 실패 시에도 에이전트 지목 문서는 가급적 포함되도록 정렬한다.
        fallback_docs = sorted(
            retrieved_docs, 
            key=lambda d: get_document_id(d) in essential_doc_ids, 
            reverse=True
        )
        return {
            "retrieved_docs": fallback_docs[:total_k],
            "rerank_count": 0,
        }
    else:
        final_docs, rerank_metadata = _apply_two_pool_selection(
            reranked_docs=reranked_docs,
            essential_doc_ids=essential_doc_ids,
            total_k=total_k,
        )

        # 에이전트가 ToolMessage로 본 적 없는 문서가 최종 답변 풀에 얼마나 들어왔는지 측정.
        # "에이전트 시야 ⊂ 시스템 풀" 분리의 실질적 가치를 정량화한다.
        agent_seen = set(state.get("agent_seen_doc_ids") or [])
        unseen_in_final = sum(
            1 for d in final_docs if get_document_id(d) not in agent_seen
        )
        rerank_metadata["agent_seen_total"] = len(agent_seen)
        rerank_metadata["unseen_in_final"] = unseen_in_final

        # 에이전트 지목 ∩ rerank top_k 통과 문서 (양쪽이 인정한 신뢰도 높은 문서).
        # doc_id를 SoT로 보관 — 답변 노드가 retrieved_docs 순서로 인덱스 매핑.
        # 답변 LLM이 실제로 보는 1-base 인덱스도 metadata에 남겨 Langfuse에서 감사 가능하게 한다.
        confirmed_essential = []
        confirmed_indices = []
        for idx, doc in enumerate(final_docs, start=1):
            doc_id = get_document_id(doc)
            if doc_id in essential_doc_ids:
                confirmed_essential.append(doc_id)
                confirmed_indices.append(idx)
        rerank_metadata["confirmed_essential_count"] = len(confirmed_essential)
        rerank_metadata["confirmed_essential_indices"] = confirmed_indices

        groups = build_doc_groups(final_docs)
        rerank_metadata["source_distribution"] = dict(
            Counter(
                g.representative.metadata.get("source", "unknown")
                for g in groups
            )
        )
        rerank_metadata["stop_reason"] = (
            state.get("agent_stop_reason") or "by_choice"
        )

        logger.info(
            "rerank_node_completed",
            pipeline_type=pipeline_type,
            final_doc_count=len(final_docs),
            total_k=total_k,
            bypass_count=rerank_metadata["bypass_count"],
            bypass_budget=rerank_metadata["bypass_budget"],
            reranker_essential_recall=rerank_metadata["reranker_essential_recall"],
            stop_reason=rerank_metadata["stop_reason"],
            agent_seen_total=len(agent_seen),
            unseen_in_final=unseen_in_final,
            confirmed_essential_count=len(confirmed_essential),
        )
        
        return {
            "retrieved_docs": final_docs,
            "rerank_count": rerank_count + 1,
            "rerank_metadata": rerank_metadata,
            "confirmed_essential_doc_ids": confirmed_essential,
        }


def _apply_two_pool_selection(
    reranked_docs: list[Document],
    essential_doc_ids: set[str],
    total_k: int,
) -> tuple[list[Document], dict]:
    """reranker top-K를 두 풀로 분리해 essential cut-off 문서를 보장한다.

    Pool A: rerank score 상위 (total_k - len(pool_b))개
    Pool B: reranker가 cut-off한 essential 문서 중 score 상위 essential_budget개
    essential_budget = floor(total_k * 0.3)
    """
    if not reranked_docs:
        return [], {
            "reranker_essential_recall": 0.0,
            "cut_off_essential_count": 0,
            "bypass_count": 0,
            "bypass_budget": 0,
        }

    essential_budget = math.floor(total_k * 0.3)
    reranker_top_k_ids = {get_document_id(d) for d in reranked_docs[:total_k]}

    reranker_essential_recall = (
        len(essential_doc_ids & reranker_top_k_ids) / len(essential_doc_ids)
        if essential_doc_ids
        else 0.0
    )

    cut_off_essential = [
        d for d in reranked_docs[total_k:]
        if get_document_id(d) in essential_doc_ids
    ]

    pool_b = sorted(
        cut_off_essential,
        key=lambda d: d.metadata.get("relevance_score", 0.0),
        reverse=True,
    )[:essential_budget]

    bypass_ids = {get_document_id(d) for d in pool_b}
    pool_a = reranked_docs[: total_k - len(pool_b)]
    final_docs = pool_a + pool_b

    rank_map = {
        get_document_id(d): rank
        for rank, d in enumerate(reranked_docs, start=1)
    }
    for doc in final_docs:
        doc_id = get_document_id(doc)
        doc.metadata["original_rerank_score"] = doc.metadata.get(
            "relevance_score", 0.0
        )
        doc.metadata["is_agent_essential"] = doc_id in essential_doc_ids
        doc.metadata["reranker_rank"] = rank_map.get(doc_id, -1)
        doc.metadata["selection_pool"] = (
            "essential_bypass" if doc_id in bypass_ids else "reranker"
        )

    metadata = {
        "reranker_essential_recall": reranker_essential_recall,
        "cut_off_essential_count": len(cut_off_essential),
        "bypass_count": len(pool_b),
        "bypass_budget": essential_budget,
    }

    return final_docs, metadata


def _resolve_total_k(pipeline_type: str) -> int:
    """파이프라인 타입에 따라 최종적으로 LLM에게 전달할 문서 개수(K)를 결정한다."""
    if pipeline_type == "complex":
        return 20
    elif pipeline_type == "standard":
        return 15
    else:  # simple, reuse 등
        return 10


def _validate_retrieved_docs(
    retrieved_docs: list[Document],
) -> list[Document]:
    valid_docs = []

    # page_content 길이 제한에 대한 방어 로직을 수행한다 (AWS Bedrock Cohere Rerank 3.5).
    for doc in retrieved_docs:
        content = doc.page_content
        if len(content) <= MAX_RERANK_DOCUMENT_TEXT_LENGTH:
            valid_docs.append(doc)
            continue
        truncated_doc = deepcopy(doc)
        truncated_doc.page_content = content[:MAX_RERANK_DOCUMENT_TEXT_LENGTH]
        valid_docs.append(truncated_doc)

    return valid_docs


# Deprecated
def _select_diverse_top_k(
    reranked_docs: list[Document], total_k: int, min_guarantee: int
) -> list[Document]:
    """Rerank된 소스 타입들이 골고루 섞이도록 동적으로 Top K를 선정한다."""

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
