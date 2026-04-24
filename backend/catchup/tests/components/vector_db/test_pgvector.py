import unittest
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.models import SourceType


class TestPGVectorServiceWeightedSearch(unittest.TestCase):
    def setUp(self):
        self.mock_engine = MagicMock()
        self.mock_embeddings = MagicMock()
        self.mock_session_factory = MagicMock()
        self.mock_session = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = (
            self.mock_session
        )

        with patch("catchup.components.vector_db.pgvector.pgvector.PGVector"):
            self.service = PGVectorService(
                postgresql_engine=self.mock_engine,
                embeddings=self.mock_embeddings,
                session_factory=self.mock_session_factory,
            )

    def test_weighted_keyword_search_sql_structure(self):
        self.mock_session.execute.return_value.fetchall.return_value = []

        # 1. Both mode (Default)
        self.service._weighted_keyword_search(query="hybrid test")
        args, _ = self.mock_session.execute.call_args
        sql_both = str(args[0])
        self.assertIn("(CASE WHEN (e.cmetadata ->> 'title') LIKE likequery(:query) THEN 2 ELSE 0 END)", sql_both)
        self.assertIn("(bigm_similarity(e.cmetadata ->> 'title', :query) * 2.0)", sql_both)

        # 2. Title mode
        self.service._weighted_keyword_search(query="title test", search_mode="title")
        args, _ = self.mock_session.execute.call_args
        sql_title = str(args[0])
        self.assertIn("(CASE WHEN (e.cmetadata ->> 'title') LIKE likequery(:query) THEN 1 ELSE 0 END)", sql_title)
        self.assertNotIn("'contextual_content'", sql_title) # Content 필드 배제 확인

        # 3. Content mode
        self.service._weighted_keyword_search(query="content test", search_mode="content")
        args, _ = self.mock_session.execute.call_args
        sql_content = str(args[0])
        self.assertIn("(CASE WHEN (e.cmetadata ->> 'contextual_content') LIKE likequery(:query) THEN 1 ELSE 0 END)", sql_content)
        self.assertNotIn("'title'", sql_content) # Title 필드 배제 확인

    def test_weighted_keyword_search_results_conversion(self):
        # Mock results: (document, metadata, id, exact_match_boost, similarity_score)
        self.mock_session.execute.return_value.fetchall.return_value = [
            ("Doc 1", {"title": "Matched Title"}, "id1", 3, 2.5),
            ("Doc 2", {"title": "Other"}, "id2", 1, 0.5),
        ]

        results = self.service._weighted_keyword_search(query="test")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].page_content, "Doc 1")
        self.assertEqual(results[0].metadata["title"], "Matched Title")
        self.assertEqual(results[1].page_content, "Doc 2")

    def test_hybrid_search_3way_rrf_logic(self):
        # hybrid_search가 내부적으로 3개의 retriever를 호출하고 weighted_reciprocal_rank를 사용하는지 확인
        # vector_store.as_retriever()와 PostgresFTSRetriever를 적절히 모킹해야 함
        
        with patch.object(self.service.vector_store, "as_retriever") as mock_vector_retriever, \
             patch("catchup.components.vector_db.pgvector.pgvector.PostgresFTSRetriever") as mock_fts_class:
            
            # Setup mocks
            mock_vector_retriever.return_value.invoke.return_value = [Document(page_content="V1", id="id1")]
            
            mock_title_retriever = MagicMock()
            mock_title_retriever.invoke.return_value = [Document(page_content="T1", id="id1")]
            
            mock_content_retriever = MagicMock()
            mock_content_retriever.invoke.return_value = [Document(page_content="C1", id="id2")]
            
            # Side effect for PostgresFTSRetriever instances (title, then content)
            mock_fts_class.side_effect = [mock_title_retriever, mock_content_retriever]
            
            # Execute
            results = self.service.hybrid_search(query="test", k=2)
            
            # Verify
            self.assertEqual(len(results), 2)
            # id1은 Vector와 Title에서 매칭되어 상위권 예상
            self.assertEqual(results[0].id, "id1")
            self.assertEqual(results[1].id, "id2")
            
            # Check weights passed to RRF (via internal _hybrid_search_chain)
            # 여기서는 호출 여부와 결과 수 정도로 검증
            self.assertTrue(mock_vector_retriever.called)
            self.assertEqual(mock_fts_class.call_count, 2)

    def test_hybrid_search_score_threshold_filtering(self):
        # score_threshold 이하의 semantic 결과가 필터링되는지 확인
        with patch.object(self.service.vector_store, "similarity_search_with_score") as mock_sim_search, \
             patch("catchup.components.vector_db.pgvector.pgvector.PostgresFTSRetriever") as mock_fts_class:
            
            # High score (0.8) and Low score (0.2)
            mock_sim_search.return_value = [
                (Document(page_content="High", id="id_high"), 0.8),
                (Document(page_content="Low", id="id_low"), 0.2)
            ]
            
            # Keyword 결과는 빈 리스트 (Semantic만 테스트)
            mock_retriever = MagicMock()
            mock_retriever.invoke.return_value = []
            mock_fts_class.return_value = mock_retriever
            
            # Default threshold (0.4)
            results = self.service.hybrid_search(query="test", score_threshold=0.4)
            
            # id_low (0.2)는 필터링되어야 함
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].id, "id_high")

    def test_unknown_source_relevance_score(self):
        from catchup.rag.schemas.sources import BaseSource
        
        # Mock document with no source (will trigger fallback to UnknownSource)
        doc = Document(
            page_content="Content",
            metadata={"score": 0.7}, # RRF score
            id="unknown_id"
        )
        
        # Should not raise TypeError: got multiple values for keyword argument 'relevance_score'
        source = BaseSource.from_document(
            index=1,
            doc=doc,
            relevance_score=doc.metadata["score"]
        )
        
        self.assertEqual(source.relevance_score, 0.7)
        self.assertEqual(source.title, "Unknown Source")

