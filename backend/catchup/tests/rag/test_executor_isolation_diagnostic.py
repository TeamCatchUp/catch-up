"""
Chat LLM과 Reranker가 전용 executor를 사용하는지 검증한다.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.components.llm.isolated_chat_bedrock import IsolatedChatBedrock
from catchup.components.reranker.service import AwsBedrockRerankService
from catchup.utils.executors import service_executors


class TestExecutorIsolationDiagnostic(IsolatedAsyncioTestCase):

    def setUp(self):
        # LLM 테스트용 executor 설정
        self._original_llm_executor = service_executors.llm_executor
        self._test_llm_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm-test")
        service_executors.llm_executor = self._test_llm_executor

        # Rerank 테스트용 executor 설정
        self._original_rerank_executor = service_executors.rerank_executor
        self._test_rerank_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rerank-test")
        service_executors.rerank_executor = self._test_rerank_executor

    def tearDown(self):
        self._test_llm_executor.shutdown(wait=False)
        service_executors.llm_executor = self._original_llm_executor
        
        self._test_rerank_executor.shutdown(wait=False)
        service_executors.rerank_executor = self._original_rerank_executor

    async def test_isolated_chat_bedrock_uses_llm_executor(self):
        """IsolatedChatBedrock._agenerate 호출 시 service_executors.llm_executor가 사용되는지 확인"""
        
        # IsolatedChatBedrock은 langchain_core.run_in_executor를 사용함
        # catchup.components.llm.isolated_chat_bedrock.run_in_executor를 패치해야 함
        
        captured_executors = []

        async def fake_run_in_executor(executor, func, *args, **kwargs):
            captured_executors.append(executor)
            # 실제 실행은 하지 않고 가짜 결과 반환
            return MagicMock()

        llm = IsolatedChatBedrock(model_id="anthropic.claude-3-sonnet-20240229-v1:0", region_name="us-east-1")
        
        with patch("catchup.components.llm.isolated_chat_bedrock.run_in_executor", side_effect=fake_run_in_executor):
            await llm._agenerate(messages=[MagicMock()])

        self.assertIn(service_executors.llm_executor, captured_executors, "IsolatedChatBedrock은 service_executors.llm_executor를 사용해야 합니다.")

    async def test_reranker_service_uses_rerank_executor(self):
        """AwsBedrockRerankService.rerank 호출 시 service_executors.rerank_executor가 사용되는지 확인"""
        
        loop = asyncio.get_running_loop()
        captured_executors = []

        async def fake_run_in_executor(executor, func, *args, **kwargs):
            captured_executors.append(executor)
            return []

        service = AwsBedrockRerankService()
        
        with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
            await service.rerank(query="test", documents=[MagicMock()])

        self.assertIn(service_executors.rerank_executor, captured_executors, "AwsBedrockRerankService는 service_executors.rerank_executor를 사용해야 합니다.")
