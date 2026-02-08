from functools import lru_cache

from catchup.components.graph_db.neo4j.neo4j import Neo4jRetrievalService


@lru_cache
def get_graph_db_service() -> Neo4jRetrievalService:
    return Neo4jRetrievalService()
