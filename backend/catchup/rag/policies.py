def get_node_inprogress_payload(node: str, input_data: dict) -> dict | None:
    """on_chain_start 시점에 in_progress 이벤트에 추가할 페이로드를 반환한다.

    대부분의 노드는 None을 반환해 static_reasoning만 사용한다.
    input_data에서 동적 content가 필요한 노드만 여기서 처리한다.
    """
    if node == "search_vector_db":
        queries = input_data.get("vector_search_queries", [])
        return {
            "content": {
                "queries": [
                    {"vector": q.query, "keyword": q.keyword_tokens}
                    for q in queries
                ]
            }
        }
    return None


def get_node_completed_payload(node: str, output_data: dict) -> dict | None:
    """on_chain_end 시점에 completed 이벤트 페이로드를 반환한다.

    반환값이 None이면 stream processor가 이 노드의 completed를 처리하지 않는다.
    반환값이 dict(빈 dict 포함)이면 그 내용으로 completed 이벤트를 발행한다.
    """
    if node == "rewrite":
        rewritten = output_data.get("rewritten_query")
        return {"content": {"query": rewritten}} if rewritten else None

    if node == "search_vector_db":
        count = len(output_data.get("retrieved_docs", []))
        return {"reasoning": f"{count}건의 문서를 찾았어요."}

    if node == "rerank":
        from catchup.rag.nodes.utils import build_doc_groups
        docs = output_data.get("retrieved_docs", [])
        groups = build_doc_groups(docs)
        source_distribution: dict[str, int] = {}
        for group in groups:
            source = group.representative.metadata.get("source", "unknown")
            source_distribution[source] = source_distribution.get(source, 0) + 1
        return {"content": {"source_distribution": source_distribution}}

    return None


CITATION_POLICY_MESSAGE = (
    "[CITATION REMINDER]"
    "ALERT: You must strictly comply with the citation rules "
    "provided in the system prompt above. "
    "Do not omit the <citations> block and do not violate placement rules."
)

FALLBACK_ANSWER = (
    "죄송합니다. 답변을 생성하는 중에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
)

NO_DOCUMENTS_ANSWER = (
    "관련 자료를 찾지 못했어요. "
    "질문을 더 구체적으로 표현하거나, 다른 키워드로 다시 시도해 주세요."
)
