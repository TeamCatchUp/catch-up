import unittest
from unittest.mock import MagicMock
from unittest.mock import patch
from catchup.components.vector_db.pgvector.pgvector import PGBigmRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

class TestPGVectorReproduction(unittest.TestCase):
    def setUp(self):
        self.mock_session_factory = MagicMock()
        self.mock_session = MagicMock()
        self.mock_session_factory.return_value.__enter__.return_value = self.mock_session
        
        self.retriever = PGBigmRetriever(
            session_factory=self.mock_session_factory,
            collection_name="test_collection",
            k=4,
            weighted=True,
            search_mode="both"
        )

    def test_multi_token_query_handling(self):
        """
        [Corrected Behavior] 
        리스트로 전달된 키워드들이 각각 독립적으로 매칭되어야 함.
        """
        query_list = ["로그인", "팀원C"]
        self.mock_session.execute.return_value.fetchall.return_value = []
        
        self.retriever._get_relevant_documents(
            query_list, 
            run_manager=CallbackManagerForRetrieverRun.get_noop_manager()
        )
        
        args, _ = self.mock_session.execute.call_args
        sql = str(args[0])
        params = args[1]
        
        # 1. 단일 'query' 파라미터로 합쳐지지 않고 각 토큰이 전달되어야 함 (또는 SQL 내에서 각 토큰 처리)
        # 개선된 로직은 token_0, token_1 등을 사용함
        self.assertIn("token_0", params)
        self.assertIn("token_1", params)

    def test_no_ef_search_in_bigm(self):
        """
        [Corrected Behavior]
        pg_bigm 키워드 검색 시 hnsw.ef_search 설정을 호출하지 않아야 함.
        """
        self.mock_session.execute.return_value.fetchall.return_value = []
        
        self.retriever._get_relevant_documents(
            "test", 
            run_manager=CallbackManagerForRetrieverRun.get_noop_manager()
        )
        
        calls = self.mock_session.execute.call_args_list
        for call in calls:
            statement = str(call[0][0])
            self.assertNotIn("hnsw.ef_search", statement)
        
        # 대신 pg_bigm.similarity_limit 설정이 있는지 확인 (선택 사항)
        set_limit_call_exists = any("pg_bigm.similarity_limit" in str(c[0][0]) for c in calls)
        self.assertTrue(set_limit_call_exists, "pg_bigm.similarity_limit should be set")

    def test_search_mode_respected_unified(self):
        """
        [Corrected Behavior]
        통합 로직에서 search_mode가 'title'일 때 content 필드를 검색하지 않는지 확인.
        """
        self.retriever.search_mode = "title"
        self.mock_session.execute.return_value.fetchall.return_value = []
        
        self.retriever._get_relevant_documents(
            "test", 
            run_manager=CallbackManagerForRetrieverRun.get_noop_manager()
        )
        
        args, _ = self.mock_session.execute.call_args
        sql = str(args[0])
        
        # 'title' 모드에서는 title 필드만 검색하고 contextual_content는 제외해야 함
        self.assertIn("e.cmetadata ->> 'title'", sql)
        self.assertNotIn("e.cmetadata ->> 'contextual_content'", sql)

if __name__ == "__main__":
    unittest.main()
