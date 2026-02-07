import logging
from typing import Any
from langchain_neo4j import Neo4jGraph

from catchup.configs.config import settings

logger = logging.getLogger(__name__)


class Neo4jRetrievalService:
    def __init__(self):
        try:
            self.graph = Neo4jGraph(
                url=settings.NEO4J_URI,
                username=settings.NEO4J_USER,
                password=settings.NEO4J_PASSWORD,
            )

            logger.info("Neo4j connection successfully established.")

        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            raise e

    def get_instance(self) -> Neo4jGraph:
        return self.graph

    def query(self, query: str, params: dict[str, Any] = None) -> list[dict[str, Any]]:
        try:
            return self.graph.query(query, params=params)
        except Exception as e:
            logger.warning(f"Cypher 쿼리 실행 실패: {e}")
            return []

    def get_context_by_anchors(
        self, anchor_ids: list[str], limit: int = 50
    ) -> list[dict[str, Any]]:
        if not anchor_ids:
            return []

        # TODO: Full Scan 방지를 위해 Index 설정 여부 확인 (필수)
        cypher = """
        MATCH (start_node)
        WHERE start_node.id IN $anchor_ids
        
        // 연결된 관계 조회 (방향 무관)
        MATCH (start_node)-[r]-(connected_node)
        
        // 결과 반환 (LLM이 읽기 좋은 형태로 가공)
        RETURN 
            start_node.id AS source,
            type(r) AS relation,
            connected_node.id AS target,
            coalesce(connected_node.summary, connected_node.name, connected_node.content) AS context_text,
            labels(connected_node) AS target_labels
        LIMIT $limit
        """

        return self.query(
            query=cypher, params={"anchor_ids": anchor_ids, "limit": limit}
        )
