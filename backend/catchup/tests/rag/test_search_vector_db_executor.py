"""
search_vector_db가 vector_search 전용 executor를 사용하는지 검증한다.

목적:
  - hybrid_search 호출이 asyncio 기본 executor(sync worker와 공유)가 아닌
    rag_executors.vector_search로 실행됨을 보장한다.
  - 이 테스트가 통과하면 sync worker full sync 중 chat 타임아웃이 발생하지 않는다.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.rag.executors import rag_executors
from catchup.rag.nodes.search_vector_db.search_vector_db import (
    _get_hybrid_search_results,
)
from catchup.rag.schemas.structures import VectorDbSearchQuery


class TestSearchVectorDbExecutor(IsolatedAsyncioTestCase):

    def setUp(self):
        self._original_executor = rag_executors.vector_search
        self._test_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rag-vector-search-test")
        rag_executors.vector_search = self._test_executor

    def tearDown(self):
        self._test_executor.shutdown(wait=False)
        rag_executors.vector_search = self._original_executor

    async def test_uses_vector_search_executor(self):
        """run_in_executor 호출 시 rag_executors.vector_search가 전달되는지 확인"""
        captured_executors: list = []
        loop = asyncio.get_running_loop()

        async def fake_run_in_executor(executor, fn, *args):
            captured_executors.append(executor)
            return []

        mock_service = MagicMock()
        queries = [VectorDbSearchQuery(query="테스트 쿼리", reasoning="test")]

        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            await _get_hybrid_search_results(mock_service, queries)

        self.assertEqual(len(captured_executors), 1)
        self.assertIs(
            captured_executors[0],
            rag_executors.vector_search,
            "asyncio 기본 executor가 아닌 rag_executors.vector_search가 사용되어야 합니다.",
        )

    async def test_uses_vector_search_executor_for_multiple_queries(self):
        """쿼리가 여러 개일 때 모두 rag_executors.vector_search으로 실행되는지 확인"""
        captured_executors: list = []
        loop = asyncio.get_running_loop()

        async def fake_run_in_executor(executor, fn, *args):
            captured_executors.append(executor)
            return []

        mock_service = MagicMock()
        queries = [
            VectorDbSearchQuery(query=f"쿼리 {i}", reasoning="test")
            for i in range(3)
        ]

        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            await _get_hybrid_search_results(mock_service, queries)

        self.assertEqual(len(captured_executors), 3)
        for i, executor in enumerate(captured_executors):
            self.assertIs(
                executor,
                rag_executors.vector_search,
                f"쿼리 {i}: rag_executors.vector_search가 사용되어야 합니다.",
            )

    async def test_not_using_default_executor(self):
        """기본 executor(None)가 사용되지 않는지 확인"""
        captured_executors: list = []
        loop = asyncio.get_running_loop()

        async def fake_run_in_executor(executor, fn, *args):
            captured_executors.append(executor)
            return []

        mock_service = MagicMock()
        queries = [VectorDbSearchQuery(query="기본 executor 테스트", reasoning="test")]

        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            await _get_hybrid_search_results(mock_service, queries)

        for executor in captured_executors:
            self.assertIsNotNone(
                executor,
                "기본 executor(None)가 사용되면 sync worker와 thread pool을 공유하게 됩니다.",
            )
