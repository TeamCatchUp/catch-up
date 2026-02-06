"""
PGVector 벡터 데이터베이스 모듈

PostgreSQL의 pgvector 확장을 사용하여 벡터 검색 제공.
Jira 데이터의 임베딩 저장 및 시맨틱 검색에 사용.
"""

from catchup.components.vector_db.pgvector.repository import PGVectorRepository

__all__ = ["PGVectorRepository"]
