"""
AwsBedrockRerankService가 rag_executors.bedrock_rerank를 사용하는지 검증한다.

목적:
  - compress_documents 호출이 asyncio 기본 executor가 아닌
    rag_executors.bedrock_rerank로 실행됨을 보장한다.
  - executor 생명주기가 rag_executors에서 관리됨을 보장한다.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.rag.executors import rag_executors


class TestAwsBedrockRerankServiceExecutor(IsolatedAsyncioTestCase):

    def setUp(self):
        self._original_bedrock_rerank = rag_executors.bedrock_rerank
        self._test_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bedrock-rerank-test")
        rag_executors.bedrock_rerank = self._test_executor

    def tearDown(self):
        self._test_executor.shutdown(wait=False)
        rag_executors.bedrock_rerank = self._original_bedrock_rerank

    def _make_service(self):
        """AWS 연결 없이 AwsBedrockRerankService 인스턴스를 생성한다."""
        from catchup.components.reranker.service import AwsBedrockRerankService

        with patch(
            "catchup.components.reranker.service.create_aws_client",
            return_value=MagicMock(),
        ), patch(
            "catchup.components.reranker.service.BedrockRerank",
            return_value=MagicMock(),
        ):
            return AwsBedrockRerankService()

    def test_service_has_no_own_executor(self):
        """서비스가 자체 executor를 소유하지 않는지 확인 (생명주기는 rag_executors가 관리)"""
        service = self._make_service()
        self.assertFalse(
            hasattr(service, "_executor"),
            "executor 소유권이 서비스에 있으면 shutdown이 누락될 수 있습니다.",
        )

    async def test_rerank_uses_rag_executors_bedrock_rerank(self):
        """rerank()가 rag_executors.bedrock_rerank로 run_in_executor를 호출하는지 확인"""
        service = self._make_service()
        captured_executors: list = []
        loop = asyncio.get_running_loop()

        async def fake_run_in_executor(executor, fn, *args):
            captured_executors.append(executor)
            doc = Document(page_content="test", metadata={"_original_id": "1"})
            return [doc]

        documents = [Document(id="1", page_content="테스트 문서", metadata={})]

        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            await service.rerank(query="테스트", documents=documents, top_n=5)

        self.assertEqual(len(captured_executors), 1)
        self.assertIs(
            captured_executors[0],
            rag_executors.bedrock_rerank,
            "rag_executors.bedrock_rerank가 사용되어야 합니다.",
        )

    async def test_rerank_not_using_default_executor(self):
        """기본 executor(None)가 사용되지 않는지 확인"""
        service = self._make_service()
        captured_executors: list = []
        loop = asyncio.get_running_loop()

        async def fake_run_in_executor(executor, fn, *args):
            captured_executors.append(executor)
            doc = Document(page_content="test", metadata={"_original_id": "1"})
            return [doc]

        documents = [Document(id="1", page_content="테스트 문서", metadata={})]

        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            await service.rerank(query="테스트", documents=documents, top_n=5)

        for executor in captured_executors:
            self.assertIsNotNone(
                executor,
                "기본 executor(None)가 사용되면 sync worker와 thread pool을 공유하게 됩니다.",
            )

    async def test_rerank_empty_documents_skips_executor(self):
        """문서가 없을 때 executor를 호출하지 않는지 확인"""
        service = self._make_service()
        loop = asyncio.get_running_loop()
        run_in_executor_called = False

        async def fake_run_in_executor(executor, fn, *args):
            nonlocal run_in_executor_called
            run_in_executor_called = True
            return []

        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            result = await service.rerank(query="테스트", documents=[], top_n=5)

        self.assertEqual(result, [])
        self.assertFalse(run_in_executor_called, "빈 문서 목록에서 executor가 호출되면 안 됩니다.")


class TestRagExecutorsLifecycle(IsolatedAsyncioTestCase):
    """rag_executors의 초기화 및 shutdown 동작을 검증한다."""

    def test_shutdown_handles_none_executors(self):
        """`init()` 전에 `shutdown()`을 호출해도 에러가 나지 않는지 확인"""
        from catchup.rag.executors import RagExecutors
        executors = RagExecutors()
        try:
            executors.shutdown()
        except Exception as e:
            self.fail(f"초기화 전 shutdown()이 예외를 발생시켰습니다: {e}")

    def test_init_creates_all_executors(self):
        """`init()` 호출 후 vector_search, bedrock_rerank, llm 모두 생성되는지 확인"""
        from catchup.rag.executors import RagExecutors
        executors = RagExecutors()
        executors.init(vector_search_size=5, bedrock_rerank_size=2, llm_size=10)

        self.assertIsInstance(executors.vector_search, ThreadPoolExecutor)
        self.assertIsInstance(executors.bedrock_rerank, ThreadPoolExecutor)
        self.assertIsInstance(executors.llm, ThreadPoolExecutor)

        self.assertEqual(executors.vector_search._thread_name_prefix, "vector-search")
        self.assertEqual(executors.bedrock_rerank._thread_name_prefix, "bedrock-rerank")
        self.assertEqual(executors.llm._thread_name_prefix, "rag-llm")

        executors.shutdown(wait=False)
