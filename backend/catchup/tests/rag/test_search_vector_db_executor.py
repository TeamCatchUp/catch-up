"""
search_vector_db가 vector_search 전용 executor를 사용하는지 검증한다.

목적:
  - hybrid_search 호출이 asyncio 기본 executor(sync worker와 공유)가 아닌
    service_executors.vector_search_executor로 실행됨을 보장한다.
  - 이 테스트가 통과하면 sync worker full sync 중 chat 타임아웃이 발생하지 않는다.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.utils.executors import service_executors


class TestSearchVectorDbExecutor(IsolatedAsyncioTestCase):

    def setUp(self):
        self._original_executor = service_executors.vector_search_executor
        self._test_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rag-vector-search-test")
        service_executors.vector_search_executor = self._test_executor

    def tearDown(self):
        self._test_executor.shutdown(wait=False)
        service_executors.vector_search_executor = self._original_executor

    async def test_uses_vector_search_executor_via_batch(self):
        """hybrid_search_batch 호출 시 내부 hybrid_search가 service_executors.vector_search_executor를 사용하는지 확인"""
        captured_executors: list = []
        loop = asyncio.get_running_loop()

        # hybrid_search 내부에 있는 run_in_executor를 캡처하기 위해 loop.run_in_executor 패치
        original_run = loop.run_in_executor

        def fake_run_in_executor(executor, fn, *args):
            captured_executors.append(executor)
            # fn(payload) 형태로 호출되므로 lambda도 인자를 받아야 함
            return original_run(executor, lambda _: [], *args)

        mock_service = MagicMock()
        # 실제 PGVectorService.hybrid_search_batch 로직을 테스트하기 위해
        # 여기서는 MagicMock 대신 실제 인스턴스나 최소한의 구현이 필요할 수 있음.
        # 하지만 hybrid_search_batch는 service.hybrid_search를 호출하므로 
        # service.hybrid_search가 실제 구현체여야 내부 run_in_executor가 불림.
        
        from catchup.components.vector_db.pgvector.pgvector import PGVectorService
        
        # PGVectorService.__init__ 에서 PGVector를 생성하므로 패치 필요
        with patch("catchup.components.vector_db.pgvector.pgvector.PGVector"):
            service = PGVectorService(
                postgresql_engine=MagicMock(),
                embeddings=MagicMock(),
            )
            
            queries = [{"query": "테스트 쿼리"}]

            with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
                await service.hybrid_search_batch(queries)

        # hybrid_search는 내부적으로 3개의 executor task를 생성함 (vector, title, content)
        self.assertEqual(len(captured_executors), 3)
        for executor in captured_executors:
            self.assertIs(
                executor,
                service_executors.vector_search_executor,
                "asyncio 기본 executor가 아닌 service_executors.vector_search_executor가 사용되어야 합니다.",
            )
