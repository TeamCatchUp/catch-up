import hashlib
import json
import logging
from typing import Any

from langchain_core.documents import Document
from langchain_neo4j import GraphCypherQAChain

from catchup.components.graph_db.factory import get_graph_db_service
from catchup.components.llm.factory import get_llm_service
from catchup.rag.nodes.fallback_cypher_query.prompt import CYPHER_GENERATION_PROMPT
from catchup.rag.nodes.utils import log_node
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def fallback_cypher_query_node(state: AgentState):
    query = state["rewritten_query"]
    vector_docs = state.get("retrieved_docs", [])

    logger.info(
        f"Anchor ID 없음 -> GraphCypherQAChain으로 Fallback 수행. (Query: {query})"
    )

    graph_docs = []

    try:
        graph_service = get_graph_db_service()

        llm = get_llm_service().get_llm()
        chain = GraphCypherQAChain.from_llm(
            llm=llm,
            graph=graph_service.get_instance(),
            verbose=True,
            validate_cypher=True,
            allow_dangerous_requests=True,  # TODO: DB User -> Read Only, APOC 비활성화, 쿼리 Timeout 설정, 허용 패턴 Whitelist
            return_direct=True,  #  자연어 설명 대신 dict 검색 결과 반환 강제
            cypher_prompt=CYPHER_GENERATION_PROMPT,
        )

        # 자연어 질문 -> Cypher -> dict
        response: dict[str, Any] = await chain.ainvoke({"query": query})

        raw_results: list[dict[str, Any]] = response.get("result", "")

        if not raw_results:
            logger.warning("Graph Fallback 검색 결과 없음.")

        else:
            graph_docs = _convert_fallback_results_to_documents(
                raw_results, query, response.get("query", "")
            )
            logger.info(f"Graph Fallback 성공: {len(graph_docs)}개 문서 생성")

    except Exception as e:
        logger.warning(f"Graph DB 조회 실패: {e}")
        return {"retrieved_docs": vector_docs}

    combined_docs = vector_docs + graph_docs

    return {"retrieved_docs": combined_docs}


def _convert_fallback_results_to_documents(
    results: list[dict[str, Any]], original_query: str, generated_cypher: str
) -> list[Document]:
    documents = []

    query_hash = _hash(original_query)

    for row in results:
        content_str = json.dumps(row, ensure_ascii=False)

        content_hash = _hash(content_str)

        doc_id = _resolve_document_id(row, query_hash, content_hash)

        metadata = {
            "db_origin": "graph",
            "strategy": "cypher",
            "original_query": original_query,
            "generated_cypher": generated_cypher,
            "raw_data": content_str,
        }

        document = Document(
            page_content=f"[Graph Search Result] {content_str}",
            metadata=metadata,
            id=doc_id,
        )

        documents.append(document)

    return documents


def _hash(data: str):
    return hashlib.md5(data.encode("utf-8")).hexdigest()[:8]


def _resolve_document_id(
    row: dict[str, Any], query_hash: str, content_hash: str
) -> str:
    source = row.get("source")
    rel = row.get("rel")
    target = row.get("target")

    if source and rel and target:
        safe_s = str(source).replace(":", "_")
        safe_t = str(target).replace(":", "_")
        doc_id = f"graph:fallback:{safe_s}:{rel}:{safe_t}"
    else:
        doc_id = f"graph:fallback:{query_hash}:{content_hash}"

    return doc_id
