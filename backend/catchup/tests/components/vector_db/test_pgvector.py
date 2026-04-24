import unittest
from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.models import SourceType


class TestPGVectorServiceManualSearch(unittest.TestCase):
    def setUp(self):
        self.mock_engine = MagicMock()
        self.mock_embeddings = MagicMock()
        self.mock_session_factory = MagicMock()
        self.mock_session = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = (
            self.mock_session
        )

        # PGVectorService 초기화 (vector_store 생성 부분은 patch로 우회)
        with patch("catchup.components.vector_db.pgvector.pgvector.PGVector"):
            self.service = PGVectorService(
                postgresql_engine=self.mock_engine,
                embeddings=self.mock_embeddings,
                session_factory=self.mock_session_factory,
            )

    def test_manual_keyword_search_basic(self):
        # Mock results (document, metadata, id, exact_match_boost, similarity_score)
        self.mock_session.execute.return_value.fetchall.return_value = [
            ("Content 1", {"source": "slack"}, "id1", 1, 1.0),
            ("Content 2", {"source": "jira"}, "id2", 0, 0.5),
        ]

        results = self.service.manual_keyword_search(keyword="test")

        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], Document)
        self.assertEqual(results[0].page_content, "Content 1")

        # SQL 호출 검증
        args, kwargs = self.mock_session.execute.call_args
        sql_text = str(args[0])
        self.assertIn("langchain_pg_embedding", sql_text)
        self.assertIn("LIKE likequery(:query)", sql_text) # Exact match boost & filter
        self.assertIn("=% :query", sql_text)         # Similarity filter
        self.assertIn("ORDER BY", sql_text)
        self.assertIn("exact_match_boost DESC", sql_text)
        self.assertIn("similarity_score DESC", sql_text)

        params = args[1]
        self.assertEqual(params["query"], "test")
        self.assertNotIn("like_query", params) # like_query 파라미터는 더 이상 사용하지 않음
        self.assertEqual(params["limit"], 20)
        self.assertEqual(params["offset"], 0)

    def test_manual_keyword_search_with_filters(self):
        self.mock_session.execute.return_value.fetchall.return_value = []

        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)

        self.service.manual_keyword_search(
            keyword="test",
            limit=10,
            offset=5,
            integrations=[SourceType.SLACK, SourceType.JIRA],
            start_date=start_date,
            end_date=end_date,
        )

        args, kwargs = self.mock_session.execute.call_args
        params = args[1]
        sql_text = str(args[0])

        self.assertEqual(params["limit"], 10)
        self.assertEqual(params["offset"], 5)
        self.assertEqual(params["tools"], ["slack", "jira"])
        self.assertEqual(params["start_date"], start_date)
        self.assertEqual(params["end_date"], end_date)
        self.assertIn("BETWEEN :start_date AND :end_date", sql_text)
        self.assertIn("= ANY(:tools)", sql_text)

