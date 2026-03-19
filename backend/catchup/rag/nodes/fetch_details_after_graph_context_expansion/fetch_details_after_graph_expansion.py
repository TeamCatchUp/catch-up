import asyncio
import logging

from langchain_core.documents import Document

from catchup.components.vector_db.factory import VectorDbProvider
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.rag.nodes.utils import log_node
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def fetch_details_after_graph_context_expansion_node(state: AgentState):

    current_docs = state.get("retrieved_docs", [])

    target_ids = _resolve_target_ids(current_docs)

    if not target_ids:
        logger.info("상세 조회가 필요한 Graph Node ID 없음.")
        return {"retrieved_docs": current_docs}

    logger.info(f"Graph 연관 문서 {len(target_ids)}건: 상세 Context 조회 시작.")

    vector_db = get_vector_db_service(VectorDbProvider.PGVECTOR)

    try:
        fetched_docs = await asyncio.to_thread(
            vector_db.get_documents_by_ids, list(target_ids)
        )

        if fetched_docs:
            logger.info(f"상세 문서 {len(fetched_docs)}개 조회 성공.")

            combined_docs = current_docs + fetched_docs
            return {"retrieved_docs": combined_docs}

        else:
            logger.warning("ID에 해당하는 문서를 Vector DB에서 찾을 수 없음.")

    except Exception as e:
        logger.error(f"Vector DB 상세 조회 중 에러 발생: {e}")

    return {"retrieved_docs": current_docs}


def _resolve_target_ids(documents: list[Document]) -> set[str]:
    target_ids = set()
    for doc in documents:
        meta = doc.metadata
        if meta.get("db_origin") == "graph":
            if "src_id" in meta:
                target_ids.add(meta["src_id"])
            if "tgt_id" in meta:
                target_ids.add(meta["tgt_id"])
    return target_ids
