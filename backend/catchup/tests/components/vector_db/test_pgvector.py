import unittest
from unittest.mock import ANY
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document
from sqlalchemy import text

from catchup.components.vector_db.pgvector.pgvector import PGBigmRetriever
from catchup.components.vector_db.pgvector.pgvector import PGVectorService


class TestPGBigmRetriever(unittest.TestCase):
    def setUp(self):
        self.mock_session_factory = MagicMock()
        self.mock_session = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = (
            self.mock_session
        )

        self.retriever = PGBigmRetriever(
            session_factory=self.mock_session_factory,
            collection_name="test_collection",
            k=4,
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

    def test_build_bigm_query_exact_mode(self):
        """exact 모드(RAG 하이브리드 검색): lower() LIKE lower(likequery()) 필터로 GIN 인덱스 사용 검증."""
        sql, _ = PGBigmRetriever.build_bigm_query(
            collection_name="test", query="Python", k=5, search_mode="exact"
        )
        sql_str = str(sql)

        self.assertIn(
            "LOWER(e.cmetadata ->> 'contextual_content') = LOWER(:token_0)", sql_str
        )
        self.assertIn(
            "lower(e.cmetadata ->> 'contextual_content') LIKE lower(likequery(:token_0))",
            sql_str,
        )
        self.assertNotIn("ILIKE", sql_str)
        self.assertNotIn("=% :token_0", sql_str)
        self.assertNotIn("'title'", sql_str)

    def test_build_bigm_query_fuzzy_mode(self):
        """fuzzy 모드(일반 키워드 검색): lower() =% lower() 유사도 필터로 GIN v2 인덱스 사용 검증."""
        sql, _ = PGBigmRetriever.build_bigm_query(
            collection_name="test", query="Python", k=5, search_mode="fuzzy"
        )
        sql_str = str(sql)

        self.assertIn(
            "LOWER(e.cmetadata ->> 'contextual_content') = LOWER(:token_0)", sql_str
        )
        self.assertIn(
            "lower(e.cmetadata ->> 'contextual_content') =% lower(:token_0)", sql_str
        )
        self.assertNotIn("ILIKE", sql_str)
        self.assertNotIn("'title'", sql_str)

    def test_do_query_does_not_set_db_parameters_inline(self):
        """DB 쿼리 실행 시 pg_bigm.similarity_limit을 인라인으로 설정하지 않는지 검증 (engine level에서 처리)."""
        self.mock_session.execute.return_value.fetchall.return_value = []

        self.retriever._do_query("SELECT 1", {})

        calls = self.mock_session.execute.call_args_list
        # 쿼리가 한 번만 실행되어야 함 (SET LOCAL이 없으므로)
        assert len(calls) == 1
        query_call = str(calls[0][0][0])
        self.assertIn("SELECT 1", query_call)
        self.assertNotIn("SET LOCAL pg_bigm.similarity_limit", query_call)

    def test_parse_tokens_from_string(self):
        result = PGBigmRetriever._parse_tokens("Apple Orange")
        self.assertEqual(set(result), {"Apple", "Orange"})

    def test_parse_tokens_from_list(self):
        result = PGBigmRetriever._parse_tokens(["Apple", "Orange", "Apple"])
        self.assertEqual(set(result), {"Apple", "Orange"})

    def test_parse_tokens_strips_empty(self):
        result = PGBigmRetriever._parse_tokens("  Apple  ")
        self.assertEqual(result, ["Apple"])

    def test_build_source_clauses_with_tool_filters(self):
        from catchup.db.models import SourceType

        params = {}
        clauses = PGBigmRetriever._build_source_clauses(
            tool_filters=[SourceType.SLACK],
            temporal_filters=None,
            params=params,
        )
        self.assertEqual(len(clauses), 1)
        self.assertIn("ANY(:tools)", clauses[0])
        self.assertEqual(params["tools"], ["slack"])

    def test_build_source_clauses_no_filters(self):
        params = {}
        clauses = PGBigmRetriever._build_source_clauses(
            tool_filters=None,
            temporal_filters=None,
            params=params,
        )
        self.assertEqual(clauses, [])
        self.assertEqual(params, {})

    def test_build_source_clauses_tool_filter_skipped_when_temporal_present(self):
        """temporal_filters가 있으면 tool_filters는 무시되고 temporal 조건만 생성된다."""
        import datetime

        from catchup.db.models import SourceType
        from catchup.rag.schemas.filters import TemporalFilter

        tf = TemporalFilter(
            tools=[SourceType.SLACK],
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 31),
            time_field="created_at",
        )
        params = {}
        clauses = PGBigmRetriever._build_source_clauses(
            tool_filters=[SourceType.GITHUB],
            temporal_filters=[tf],
            params=params,
        )
        self.assertEqual(len(clauses), 1)
        self.assertIn("BETWEEN", clauses[0])
        self.assertNotIn("ANY(:tools)", clauses[0])


class TestPGBigmRetrieverAsync(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # session.execute()는 await 대상(AsyncMock)이지만
        # 반환된 CursorResult.fetchall()은 SQLAlchemy에서 동기 호출이므로 MagicMock으로 설정
        mock_cursor_result = MagicMock()
        mock_cursor_result.fetchall.return_value = [
            ("doc content", {"source": "slack"}, "uuid-1"),
        ]
        self.mock_async_session = AsyncMock()
        self.mock_async_session.execute.return_value = mock_cursor_result

        mock_async_cm = AsyncMock()
        mock_async_cm.__aenter__.return_value = self.mock_async_session
        mock_async_cm.__aexit__.return_value = None

        self.mock_async_session_factory = MagicMock(return_value=mock_async_cm)
        self.mock_sync_session_factory = MagicMock()

        self.retriever = PGBigmRetriever(
            session_factory=self.mock_sync_session_factory,
            async_session_factory=self.mock_async_session_factory,
            collection_name="test_collection",
            k=4,
        )

    async def test_async_do_query_uses_async_session(self):
        """_async_do_query가 sync session_factory가 아닌 async_session_factory를 사용하는지 검증."""
        sql = text("SELECT 1")
        await self.retriever._async_do_query(sql, {})

        self.mock_async_session_factory.assert_called_once()
        self.mock_async_session.execute.assert_called()
        # sync session_factory는 호출되지 않아야 함
        self.mock_sync_session_factory.assert_not_called()

    async def test_async_invoke_returns_documents(self):
        """async_invoke가 DB 결과를 Document 리스트로 정상 변환하는지 검증."""
        docs = await self.retriever.async_invoke(["slack"])

        assert len(docs) == 1
        assert docs[0].page_content == "doc content"
        assert docs[0].metadata == {"source": "slack"}
        assert docs[0].id == "uuid-1"

    async def test_async_do_query_fallback_to_default_session_factory(self):
        """async_session_factory가 None일 때 AsyncSessionLocal 기본값으로 폴백되는지 검증."""
        retriever = PGBigmRetriever(
            session_factory=self.mock_sync_session_factory,
            async_session_factory=None,
            collection_name="test_collection",
            k=4,
        )
        sql = text("SELECT 1")
        mock_factory = MagicMock()
        mock_async_cm = AsyncMock()
        mock_session = AsyncMock()
        mock_cursor_result = MagicMock()
        mock_cursor_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_cursor_result
        mock_async_cm.__aenter__.return_value = mock_session
        mock_async_cm.__aexit__.return_value = None
        mock_factory.return_value = mock_async_cm

        with patch(
            "catchup.components.vector_db.pgvector.pgvector.AsyncSessionLocal",
            mock_factory,
        ):
            await retriever._async_do_query(sql, {})
            mock_factory.assert_called_once()


class TestPGVectorService:
    @pytest.fixture(autouse=True)
    def setup(self):
        mock_engine = MagicMock()
        mock_embeddings = MagicMock()
        self.mock_session_factory = MagicMock()
        self.mock_async_session_factory = MagicMock()

        with patch("catchup.components.vector_db.pgvector.pgvector.PGVector"):
            self.service = PGVectorService(
                postgresql_engine=mock_engine,
                embeddings=mock_embeddings,
                session_factory=self.mock_session_factory,
                async_session_factory=self.mock_async_session_factory,
            )

    @pytest.mark.asyncio
    async def test_hybrid_search_2way_rrf_flow(self):
        """hybrid_search가 Vector + async Content 결과를 가져와 2-way RRF를 수행하는지 검증."""
        with (
            patch.object(
                self.service.vector_store, "similarity_search_with_score"
            ) as mock_sim_search,
            patch.object(
                PGBigmRetriever, "async_invoke", new_callable=AsyncMock
            ) as mock_bigm_invoke,
        ):
            mock_sim_search.return_value = [(Document(page_content="V", id="id1"), 0.8)]
            mock_bigm_invoke.return_value = [Document(page_content="C", id="id2")]

            results = await self.service.hybrid_search(
                query="test", k=2, keyword_tokens=["test"]
            )

            assert len(results) == 2
            assert results[0].id == "id1"
            assert mock_bigm_invoke.call_count == 1

    @pytest.mark.asyncio
    async def test_hybrid_search_batch(self):
        """hybrid_search_batch가 여러 쿼리를 병렬로 처리하는지 검증."""
        queries = [{"query": "test1", "start_date": "2024-01-01"}, {"query": "test2"}]

        with patch.object(self.service, "hybrid_search") as mock_hybrid_search:
            mock_hybrid_search.return_value = [Document(page_content="result", id="id")]

            results = await self.service.hybrid_search_batch(queries=queries, k=5)

            assert len(results) == 2
            assert mock_hybrid_search.call_count == 2
            # 쿼리 인자 확인
            mock_hybrid_search.assert_any_call(
                query="test1",
                k=5,
                weights=[0.6, 0.4],
                tool_filters=None,
                temporal_filters=ANY,
                keyword_tokens=[],
            )

    def test_weighted_keyword_search_uses_unified_logic(self):
        """단독 키워드 검색 유틸도 통합된 build_bigm_query를 사용하는지 검증."""
        with patch.object(
            PGBigmRetriever, "build_bigm_query", return_value=("SELECT 1", {})
        ) as mock_build:
            self.mock_session_factory.return_value.__enter__.return_value = MagicMock()

            self.service._weighted_keyword_search(query="test")

            assert mock_build.called


if __name__ == "__main__":
    unittest.main()
