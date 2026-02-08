import logging

from langchain_core.documents import Document

from catchup.components.graph_db.factory import get_graph_db_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.rag.nodes.utils import extract_anchor_ids, log_node
from catchup.rag.state import AgentState


logger = logging.getLogger(__name__)


@log_node
async def expand_graph_context_node(state: AgentState):
    vector_docs = state.get("retrieved_docs", [])
    
    anchor_ids = extract_anchor_ids(vector_docs)
    
    logger.info(anchor_ids)

    if not anchor_ids:
        logger.warning("Graph 확장을 위한 Anchor ID가 존재하지 않음.")
        return {"retrieved_docs": vector_docs}

    logger.info(f"Anchor ID {len(anchor_ids)}개 발견. Graph 검색 수행.")

    graph_service = get_graph_db_service()

    try:
        raw_results = graph_service.get_context_by_anchors(
            anchor_ids=anchor_ids, limit=50
        )
        
        if not raw_results:
            logger.info("연결된 Graph 노드 없음.")
            return {"retrieved_docs": vector_docs}
        
    except Exception as e:
        logger.warning(f"Graph DB 조회 실패: {e}")
        return {"retrieved_docs": vector_docs}

    graph_docs = _convert_to_documents(raw_results)

    logger.info(f"Graph 확장 완료: +{len(graph_docs)}개 문서 추가.")
    logger.info(graph_docs)

    combined_docs = vector_docs + graph_docs

    return {"retrieved_docs": combined_docs}


def _convert_to_documents(results: list[dict]) -> list[Document]:
    documents = []

    for res in results:
        content = (
            f"[{res['source']}] --[{res['relation']}]--> [{res['target']}]: "
            f"{res.get('context_text', '')}"
        )

        metadata = {
            "db_origin": "graph",
            "strategy": "expand",
            "src_id": res["source"],  # anchor_id와 동일
            "tgt_id": res["target"],
            "relation": res["relation"],
            "target_labels": res.get("target_labels", []),
            "relevance_score": 1.0,
        }

        doc_id = _resolve_document_id(res)

        documents.append(Document(page_content=content, metadata=metadata, id=doc_id))

    return documents


def _resolve_document_id(result):
    safe_source = str(result["source"]).replace(":", "_")
    safe_target = str(result["target"]).replace(":", "_")

    return f"graph:expand:{safe_source}:{result['relation']}:{safe_target}"

if __name__ == "__main__":
    from catchup.components.graph_db.factory import get_graph_db_service

    # Retrieval 테스트 용 데이터 적재 스크립트
    def seed():
        print("데이터 적재 시작...")
        
        graph_service = get_graph_db_service()
        
        # Graph DB 초기화
        graph_service.query("MATCH (n) DETACH DELETE n")
        print("기존 데이터 삭제 완료")

        # 데이터 적재 쿼리
        query = """
        CREATE (kim:Person {name: 'Kim', role: 'Backend Dev'})
        CREATE (lee:Person {name: 'Lee', role: 'Data Scientist'})
        CREATE (topic_db:Topic {name: 'Database'})
        CREATE (topic_ai:Topic {name: 'AI'})
        
        CREATE (lib:Library {id: 'lib-psycopg2', name: 'psycopg2', type: 'python-library'})

        CREATE (d1:Document {id: '480e29d9-05ae-4efb-8a84-37b1e9478aad', title: 'LangChain', type: 'tech_blog'})
        CREATE (d2:Document {id: 'cd72fa82-37f5-4d94-9f52-8d4347cb88a0', title: 'PostgreSQL', type: 'wiki'})
        CREATE (d3:Document {id: '0e2f490d-68f7-484f-8b82-13c98bd54d67', title: 'Python', type: 'tech_blog'})

        CREATE (kim)-[:WROTE {timestamp: datetime()}]->(d1)
        CREATE (lee)-[:WROTE {timestamp: datetime()}]->(d3)
        CREATE (d1)-[:RELATED_TO {timestamp: datetime()}]->(topic_db)
        CREATE (d2)-[:RELATED_TO {timestamp: datetime()}]->(topic_db)
        CREATE (d3)-[:RELATED_TO {timestamp: datetime()}]->(topic_ai)

        CREATE (d3)-[:INTEGRATES_WITH {
            timestamp: datetime(), 
            context: 'Python은 psycopg2 드라이버를 사용하여 PostgreSQL과 연동할 수 있습니다.'
        }]->(d2)

        CREATE (d3)-[:USES {timestamp: datetime()}]->(lib)
        CREATE (lib)-[:CONNECTS_TO {timestamp: datetime()}]->(d2)
        """
        
        # 쿼리 실행
        graph_service.query(query)
        print("데이터 적재 완료.")
        
    seed()