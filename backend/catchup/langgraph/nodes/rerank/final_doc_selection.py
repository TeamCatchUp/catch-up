import math
from collections import Counter

import structlog
from langchain_core.callbacks import adispatch_custom_event
from langchain_core.documents import Document

from catchup.langgraph.utils import log_node
from catchup.rag.state import AgentState
from catchup.utils.documents import build_doc_groups
from catchup.utils.documents import get_document_id

logger = structlog.get_logger()


@log_node
async def select_final_docs_node(state: AgentState) -> dict:
    """reranked_docs에서 최종 문서를 선택하고 에이전틱 후처리 메타데이터를 계산한다."""
    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    if not retrieved_docs:
        await adispatch_custom_event(
            "process",
            {
                "status": "completed",
                "node": "rerank",
                "content": {"source_distribution": None},
            },
        )
        return {
            "retrieved_docs": [],
            "rerank_metadata": {},
            "confirmed_essential_doc_ids": [],
        }

    pipeline_plan = state.get("pipeline_plan")
    if pipeline_plan and hasattr(pipeline_plan, "pipeline_type"):
        pipeline_type = pipeline_plan.pipeline_type
    else:
        pipeline_type = state.get("max_pipeline_type", "standard")

    total_k = _resolve_total_k(pipeline_type)
    essential_doc_ids = set(state.get("essential_doc_ids") or [])

    final_docs, rerank_metadata = _apply_two_pool_selection(
        reranked_docs=retrieved_docs,
        essential_doc_ids=essential_doc_ids,
        total_k=total_k,
    )

    agent_seen = set(state.get("agent_seen_doc_ids") or [])
    unseen_in_final = sum(
        1 for d in final_docs if get_document_id(d) not in agent_seen
    )
    rerank_metadata["agent_seen_total"] = len(agent_seen)
    rerank_metadata["unseen_in_final"] = unseen_in_final

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
    source_distribution = dict(
        Counter(
            g.representative.metadata.get("source", "unknown")
            for g in groups
        )
    )
    rerank_metadata["source_distribution"] = source_distribution
    # rerank_node의 on_chain_end completed 이벤트를 대신 발행한다.
    # 프론트엔드에는 node="rerank" completed로 전달되어 UI 변화가 없다.
    await adispatch_custom_event(
        "process",
        {
            "status": "completed",
            "node": "rerank",
            "content": {"source_distribution": source_distribution},
        },
    )
    rerank_metadata["stop_reason"] = (
        state.get("agent_stop_reason") or "by_choice"
    )

    logger.info(
        "select_final_docs_node_completed",
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
        "rerank_metadata": rerank_metadata,
        "confirmed_essential_doc_ids": confirmed_essential,
    }


def _apply_two_pool_selection(
    reranked_docs: list[Document],
    essential_doc_ids: set,
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
    reranker_top_k_ids = {
        get_document_id(d) for d in reranked_docs[:total_k]
    }
    reranker_essential_recall = round(
        len(essential_doc_ids & reranker_top_k_ids) / len(essential_doc_ids)
        if essential_doc_ids
        else 0.0,
        4,
    )
    cut_off_essential = [
        d
        for d in reranked_docs[total_k:]
        if get_document_id(d) in essential_doc_ids
    ]
    pool_b = sorted(
        cut_off_essential,
        key=lambda d: d.metadata.get("relevance_score") or 0.0,
        reverse=True,
    )[:essential_budget]
    bypass_ids = {get_document_id(d) for d in pool_b}
    # pool_b는 reranked_docs[total_k:] 에서만 추출되므로 pool_a와 중복되지 않는다.
    pool_a = reranked_docs[: total_k - len(pool_b)]
    final_docs = pool_a + pool_b
    rank_map = {
        get_document_id(d): rank
        for rank, d in enumerate(reranked_docs, start=1)
    }
    annotated_docs = []
    for doc in final_docs:
        doc_id = get_document_id(doc)
        new_metadata = {
            **doc.metadata,
            "original_rerank_score": doc.metadata.get("relevance_score") or 0.0,
            "is_agent_essential": doc_id in essential_doc_ids,
            "reranker_rank": rank_map.get(doc_id, -1),
            "selection_pool": (
                "essential_bypass"
                if doc_id in bypass_ids
                else "reranker"
            ),
        }
        annotated_docs.append(
            Document(
                page_content=doc.page_content,
                metadata=new_metadata,
                id=doc_id,
            )
        )
    final_docs = annotated_docs
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
    else:
        return 10
