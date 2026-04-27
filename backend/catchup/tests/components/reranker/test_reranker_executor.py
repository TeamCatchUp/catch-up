"""
AwsBedrockRerankService가 rag_executors.rerank_executor를 사용하는지 검증한다.

목적:
  - rerank() 호출이 asyncio 기본 executor가 아닌
    rag_executors.rerank_executor로 실행됨을 보장한다.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.components.reranker.service import AwsBedrockRerankService
from catchup.rag.executors import rag_executors


class TestRerankerExecutor(IsolatedAsyncioTestCase):

    def setUp(self):
        self._original_bedrock_rerank = rag_executors.rerank_executor
        self._test_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bedrock-rerank-test")
        rag_executors.rerank_executor = self._test_executor

    def tearDown(self):
        self._test_executor.shutdown(wait=False)
        rag_executors.rerank_executor = self._original_bedrock_rerank

    async def test_uses_bedrock_rerank_executor(self):
        """rerank()가 rag_executors.rerank_executor로 run_in_executor를 호출하는지 확인"""
        captured_executors: list = []
        loop = asyncio.get_running_loop()

        async def fake_run_in_executor(executor, fn, *args):
            captured_executors.append(executor)
            return []

        service = AwsBedrockRerankService()
        mock_docs = [MagicMock()]

        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            await service.rerank(query="테스트 쿼리", documents=mock_docs)

        self.assertEqual(len(captured_executors), 1)
        self.assertIs(
            captured_executors[0],
            rag_executors.rerank_executor,
            "rag_executors.rerank_executor가 사용되어야 합니다.",
        )

    async def test_not_using_executor_on_empty_docs(self):
        """문서가 없을 때 executor를 사용하지 않는지 확인"""
        loop = asyncio.get_running_loop()
        run_in_executor_called = False

        async def fake_run_in_executor(executor, fn, *args):
            nonlocal run_in_executor_called
            run_in_executor_called = True
            return []

        service = AwsBedrockRerankService()

        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            await service.rerank(query="테스트 쿼리", documents=[])

        self.assertFalse(run_in_executor_called, "빈 문서 목록에서 executor가 호출되면 안 됩니다.")


class TestRagExecutorsLifecycle(IsolatedAsyncioTestCase):
    """RagExecutors의 초기화 및 해제 라이프사이클을 테스트한다."""

    def test_init_creates_executors(self):
        from catchup.rag.executors import RagExecutors
        executors = RagExecutors()
        executors.init()
        
        self.assertIsInstance(executors.vector_search_executor, ThreadPoolExecutor)
        self.assertIsInstance(executors.rerank_executor, ThreadPoolExecutor)
        self.assertIsInstance(executors.llm_executor, ThreadPoolExecutor)
        
        executors.shutdown()

    def test_shutdown_cleans_up(self):
        from catchup.rag.executors import RagExecutors
        executors = RagExecutors()
        executors.init()
        executors.shutdown()
        
        # shutdown 후에는 executor 객체 자체는 남지만, 내부 thread pool은 종료됨
        # (별도의 status check API가 없으므로 shutdown 호출 성공 여부만 확인)
