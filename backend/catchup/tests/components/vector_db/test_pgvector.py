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
        """exact 모드(RAG 하이브리드 검색): LIKE 필터 + 토큰 매칭 수 스코어링 검증."""
        sql, _ = PGBigmRetriever.build_bigm_query(
            collection_name="test", query="Python", k=5, search_mode="exact"
        )
        sql_str = str(sql)

        # LIKE 기반 필터
        self.assertIn(
            "lower(e.cmetadata ->> 'contextual_content') LIKE lower(likequery(:token_0))",
            sql_str,
        )
        # 토큰 매칭 수 스코어 (LIKE 기반 CASE WHEN — 완전 일치 = 표현식은 항상 0.0이므로 제거됨)
        self.assertIn("LIKE lower(likequery(:token_0)) THEN 1 ELSE 0", sql_str)
        # title 유사도 — Confluence/Jira/GitHub PR은 title이 채워져 있어 유효한 정렬 신호
        self.assertIn("bigm_similarity(COALESCE(e.cmetadata ->> 'title'", sql_str)
        self.assertNotIn("ILIKE", sql_str)
        self.assertNotIn("=% lower(:token_0)", sql_str)

    def test_build_bigm_query_fuzzy_mode(self):
        """fuzzy 모드(manual search): =% 필터 + bigm_similarity 스코어링 + title 시그널 검증."""
        sql, _ = PGBigmRetriever.build_bigm_query(
            collection_name="test", query="Python", k=5, search_mode="fuzzy"
        )
        sql_str = str(sql)

        # =% 기반 fuzzy 필터
        self.assertIn(
            "lower(e.cmetadata ->> 'contextual_content') =% lower(:token_0)", sql_str
        )
        # 완전 일치 부스트 스코어
        self.assertIn(
            "LOWER(e.cmetadata ->> 'contextual_content') = LOWER(:token_0)", sql_str
        )
        # Confluence/Jira title 유사도 시그널
        self.assertIn("bigm_similarity(COALESCE(e.cmetadata ->> 'title'", sql_str)
        self.assertNotIn("ILIKE", sql_str)

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

    def test_build_token_expressions_fuzzy(self):
        """Fuzzy 모드: =% 연산자와 sim_scores 생성을 검증한다."""
        params = {}
        token_filters, exact_scores, sim_scores, title_scores = (
            PGBigmRetriever._build_token_expressions(
                tokens=["Python"],
                search_mode="fuzzy",
                title_only=False,
                params=params,
            )
        )
        self.assertEqual(params["token_0"], "Python")
        self.assertEqual(len(token_filters), 1)
        self.assertIn("=% lower(:token_0)", token_filters[0])
        self.assertEqual(len(exact_scores), 1)
        self.assertEqual(len(sim_scores), 1)
        self.assertIn("bigm_similarity(e.cmetadata ->> 'contextual_content'", sim_scores[0])
        self.assertEqual(len(title_scores), 1)

    def test_build_token_expressions_exact(self):
        """Exact 모드: LIKE likequery() 연산자 및 sim_scores 비활성화를 검증한다."""
        params = {}
        token_filters, exact_scores, sim_scores, title_scores = (
            PGBigmRetriever._build_token_expressions(
                tokens=["Python"],
                search_mode="exact",
                title_only=False,
                params=params,
            )
        )
        self.assertIn("LIKE lower(likequery(:token_0))", token_filters[0])
        self.assertEqual(sim_scores, [])

    def test_build_token_expressions_title_only(self):
        """Title-only 모드: title 필드만 필터링하고 content 스코어는 생성하지 않는다."""
        params = {}
        token_filters, exact_scores, sim_scores, title_scores = (
            PGBigmRetriever._build_token_expressions(
                tokens=["Python"],
                search_mode="fuzzy",
                title_only=True,
                params=params,
            )
        )
        self.assertIn("'title'", token_filters[0])
        self.assertEqual(exact_scores, [])
        self.assertEqual(sim_scores, [])


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
            mock_sim_search.return_value = [(Document(page_content="V", id="id1"), 0.5)]
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

    def test_make_bigm_retriever_sets_common_fields(self):
        """_make_bigm_retriever가 공통 필드를 올바르게 설정하는지 검증."""
        retriever = self.service._make_bigm_retriever(
            k=50,
            offset=0,
            tool_filters=None,
            temporal_filters=None,
            search_mode="exact",
        )
        assert isinstance(retriever, PGBigmRetriever)
        assert retriever.k == 50
        assert retriever.search_mode == "exact"
        assert retriever.collection_name == self.service.collection_name

    def test_make_bigm_retriever_kwargs_override(self):
        """_make_bigm_retriever가 kwargs 오버라이드를 정상 처리하는지 검증."""
        retriever = self.service._make_bigm_retriever(
            k=10,
            offset=0,
            tool_filters=None,
            temporal_filters=None,
            title_only=True,
        )
        assert retriever.title_only is True

    @pytest.mark.asyncio
    async def test_gather_keyword_docs_2way(self):
        """title_task=None이면 2-way gather로 title_docs는 빈 리스트다."""
        v_doc = Document(page_content="V", id="v1")
        c_doc = Document(page_content="C", id="c1")

        async def _mock_content():
            return [c_doc]

        import asyncio
        loop = asyncio.get_event_loop()
        vector_task = loop.run_in_executor(None, lambda: [v_doc])

        vector_docs, content_docs, title_docs = await self.service._gather_keyword_docs(
            vector_task=vector_task,
            content_task=_mock_content(),
            title_task=None,
        )
        assert vector_docs == [v_doc]
        assert content_docs == [c_doc]
        assert title_docs == []

    @pytest.mark.asyncio
    async def test_gather_keyword_docs_3way(self):
        """title_task가 있으면 3-way gather로 title_docs가 채워진다."""
        v_doc = Document(page_content="V", id="v1")
        c_doc = Document(page_content="C", id="c1")
        t_doc = Document(page_content="T", id="t1")

        async def _mock_content():
            return [c_doc]

        async def _mock_title():
            return [t_doc]

        import asyncio
        loop = asyncio.get_event_loop()
        vector_task = loop.run_in_executor(None, lambda: [v_doc])

        vector_docs, content_docs, title_docs = await self.service._gather_keyword_docs(
            vector_task=vector_task,
            content_task=_mock_content(),
            title_task=_mock_title(),
        )
        assert vector_docs == [v_doc]
        assert content_docs == [c_doc]
        assert title_docs == [t_doc]

    @pytest.mark.asyncio
    async def test_gather_keyword_docs_no_vector_task(self):
        """vector_task=None이면 vector_docs는 빈 리스트다."""
        c_doc = Document(page_content="C", id="c1")

        async def _mock_content():
            return [c_doc]

        vector_docs, content_docs, title_docs = await self.service._gather_keyword_docs(
            vector_task=None,
            content_task=_mock_content(),
            title_task=None,
        )
        assert vector_docs == []
        assert content_docs == [c_doc]


if __name__ == "__main__":
    unittest.main()
