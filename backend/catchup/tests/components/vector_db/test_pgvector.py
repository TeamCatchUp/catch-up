import unittest
from unittest.mock import MagicMock, ANY
from unittest.mock import patch

import pytest
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from catchup.components.vector_db.pgvector.pgvector import PGVectorService, PGBigmRetriever
from catchup.db.models import SourceType


class TestPGBigmRetriever(unittest.TestCase):
    def setUp(self):
        self.mock_session_factory = MagicMock()
        self.mock_session = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = self.mock_session
        
        self.retriever = PGBigmRetriever(
            session_factory=self.mock_session_factory,
            collection_name="test_collection",
            k=4
        )

    def test_build_bigm_query_tokenization(self):
        """다중 키워드가 개별 토큰 파라미터로 분리되어 SQL에 전달되는지 검증."""
        # 1. 리스트 입력 테스트
        query_list = ["Apple", "Orange"]
        _, params_list = PGBigmRetriever.build_bigm_query(
            collection_name="test", query=query_list, k=5
        )
        token_values_list = {params_list["token_0"], params_list["token_1"]}
        self.assertEqual(token_values_list, {"Apple", "Orange"})

        # 2. 문자열 공백 분리 테스트
        query_str = "Apple Orange"
        _, params_str = PGBigmRetriever.build_bigm_query(
            collection_name="test", query=query_str, k=5
        )
        token_values_str = {params_str["token_0"], params_str["token_1"]}
        self.assertEqual(token_values_str, {"Apple", "Orange"})

    def test_build_bigm_query_case_insensitivity(self):
        """SQL 생성 시 대소문자 무시(LOWER, ILIKE) 로직이 포함되는지 검증."""
        sql, _ = PGBigmRetriever.build_bigm_query(
            collection_name="test", query="Python", k=5
        )
        sql_str = str(sql)

        # 1. Exact Match Boost 시 LOWER() 적용 확인
        self.assertIn("LOWER(e.cmetadata ->> 'title') = LOWER(:token_0)", sql_str)
        # 2. 필터링 시 ILIKE 적용 확인
        self.assertIn("ILIKE likequery(:token_0)", sql_str)
        # 3. 유사도 연산자(=%) 포함 확인
        self.assertIn("=% :token_0", sql_str)

    def test_build_bigm_query_search_mode_exclusion(self):
        """search_mode='title'일 때 content 필드가 쿼리에서 제외되는지 검증."""
        sql, _ = PGBigmRetriever.build_bigm_query(
            collection_name="test", query="test", k=5, search_mode="title"
        )
        sql_str = str(sql)

        self.assertIn("'title'", sql_str)
        self.assertNotIn("'contextual_content'", sql_str)

    def test_do_query_sets_correct_db_parameters(self):
        """DB 쿼리 실행 시 hnsw.ef_search 대신 pg_bigm.similarity_limit을 설정하는지 검증."""
        self.mock_session.execute.return_value.fetchall.return_value = []
        
        self.retriever._do_query("SELECT 1", {})
        
        calls = self.mock_session.execute.call_args_list
        set_limit_call = str(calls[0][0][0])
        
        self.assertIn("SET LOCAL pg_bigm.similarity_limit = 0.02", set_limit_call)
        self.assertNotIn("hnsw.ef_search", set_limit_call)


class TestPGVectorService:
    @pytest.fixture(autouse=True)
    def setup(self):
        mock_engine = MagicMock()
        mock_embeddings = MagicMock()
        self.mock_session_factory = MagicMock()

        with patch("catchup.components.vector_db.pgvector.pgvector.PGVector"):
            self.service = PGVectorService(
                postgresql_engine=mock_engine,
                embeddings=mock_embeddings,
                session_factory=self.mock_session_factory,
            )

    @pytest.mark.asyncio
    async def test_hybrid_search_3way_rrf_flow(self):
        """hybrid_search가 내부적으로 Vector, Title, Content 결과를 가져와 RRF를 수행하는지 검증."""
        with patch.object(self.service.vector_store, "similarity_search_with_score") as mock_sim_search, \
             patch("catchup.components.vector_db.pgvector.pgvector.PGBigmRetriever.invoke") as mock_bigm_invoke:

            mock_sim_search.return_value = [(Document(page_content="V", id="id1"), 0.8)]
            mock_bigm_invoke.side_effect = [
                [Document(page_content="T", id="id1")],
                [Document(page_content="C", id="id2")]
            ]

            results = await self.service.hybrid_search(query="test", k=2)

            assert len(results) == 2
            assert results[0].id == "id1"
            assert mock_bigm_invoke.call_count == 2

    @pytest.mark.asyncio
    async def test_hybrid_search_batch(self):
        """hybrid_search_batch가 여러 쿼리를 병렬로 처리하는지 검증."""
        queries = [
            {"query": "test1", "start_date": "2024-01-01"},
            {"query": "test2"}
        ]
        
        with patch.object(self.service, "hybrid_search") as mock_hybrid_search:
            mock_hybrid_search.return_value = [Document(page_content="result", id="id")]
            
            results = await self.service.hybrid_search_batch(queries=queries, k=5)
            
            assert len(results) == 2
            assert mock_hybrid_search.call_count == 2
            # 쿼리 인자 확인
            mock_hybrid_search.assert_any_call(
                query="test1",
                k=5,
                weights=[0.6, 0.25, 0.15],
                tool_filters=None,
                temporal_filters=ANY,
                keyword_tokens=None
            )

    def test_weighted_keyword_search_uses_unified_logic(self):
        """단독 키워드 검색 유틸도 통합된 build_bigm_query를 사용하는지 검증."""
        with patch.object(PGBigmRetriever, "build_bigm_query", return_value=("SELECT 1", {})) as mock_build:
            self.mock_session_factory.return_value.__enter__.return_value = MagicMock()

            self.service._weighted_keyword_search(query="test")

            assert mock_build.called

if __name__ == "__main__":
    unittest.main()
