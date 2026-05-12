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
        # Floor 기반 비례 가산점 부스팅을 적용한다.
        final_docs, rerank_metadata = _apply_boosting(
            reranked_docs=reranked_docs,
            essential_doc_ids=essential_doc_ids,
            total_k=total_k
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

        logger.info(
            "rerank_node_completed",
            pipeline_type=pipeline_type,
            final_doc_count=len(final_docs),
            total_k=total_k,
            boosted_count=len(rerank_metadata["boosted_ids"]),
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


def _apply_boosting(
    reranked_docs: list[Document], 
    essential_doc_ids: set[str], 
    total_k: int,
    boost_ratio: float = 0.2  # 점수 격차의 20% 만큼 가산한다.
) -> tuple[list[Document], dict]:
    """리랭커 점수의 분포에 비례하여 에이전트 지목 문서에 가산점을 부여한다.

    alignment_score는 "에이전트 지목 ∩ reranker top_k / 에이전트 지목"으로,
    essential_doc_ids가 비어 있으면(예: max_iter fallback) 0.0으로 처리한다.
    "신호 없음 = 영향 없음"으로 보아 score 평균이 위로 왜곡되지 않게 한다.
    """
    if not reranked_docs:
        return [], {"boosted_ids": [], "alignment_score": 0.0}

    scores = [d.metadata.get("relevance_score", 0.0) for d in reranked_docs]
    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score

    # Floor를 적용해 동점 상황에서도 에이전트의 판단이 타이 브레이커가 되도록 보장한다.
    effective_range = max(score_range, 0.05)
    boost_value = boost_ratio * effective_range

    boosted_docs = []
    boosted_ids = []
    
    # 리랭커 Top K 내에 에이전트 지목 문서가 얼마나 있는지 확인한다 (Alignment).
    initial_top_k_ids = {get_document_id(d) for d in reranked_docs[:total_k]}
    hits = essential_doc_ids.intersection(initial_top_k_ids)
    alignment_score = len(hits) / len(essential_doc_ids) if essential_doc_ids else 0.0

    for doc in reranked_docs:
        doc_id = get_document_id(doc)
        original_score = doc.metadata.get("relevance_score", 0.0)
        
        is_essential = doc_id in essential_doc_ids
        final_score = original_score + (boost_value if is_essential else 0.0)
        
        # 메타데이터를 업데이트한다: 답변 생성 노드와 관측에 꼭 필요한 필드만 남긴다.
        doc.metadata.update({
            "original_rerank_score": original_score,
            "boosted_score": final_score,
            "is_agent_cited": is_essential
        })
        
        if is_essential:
            boosted_ids.append(doc_id)
            logger.debug(
                "document_boosted", 
                id=doc_id, 
                original=original_score, 
                boosted=final_score,
                range=score_range
            )
        
        boosted_docs.append(doc)

    # 최종 점수 기준으로 재정렬한다.
    boosted_docs.sort(key=lambda x: x.metadata["boosted_score"], reverse=True)
    final_docs = boosted_docs[:total_k]

    # 글로벌 통계는 metadata에 모은다.
    metadata = {
        "boosted_ids": boosted_ids,
        "alignment_score": alignment_score,
        "score_range": float(score_range),
        "effective_range": float(effective_range),
        "boost_value": float(boost_value),
        "boost_ratio": boost_ratio
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
