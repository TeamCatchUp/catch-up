"""
AwsBedrockLlmService._create_llm 분기 검증.

목적:
  - extended_thinking=True일 때도 isolated 플래그와 streaming 플래그가
    무시되지 않고 그대로 반영되는지 확인한다.
"""

from __future__ import annotations

from unittest import TestCase

from langchain_aws import ChatBedrock

from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.isolated_chat_bedrock import IsolatedChatBedrock
from catchup.components.llm.service import AwsBedrockLlmService


class TestAwsBedrockLlmServiceCreateLlm(TestCase):

    def test_extended_thinking_with_isolated_returns_isolated_chat_bedrock(self):
        """extended_thinking=True, isolated=True → IsolatedChatBedrock 반환"""
        service = AwsBedrockLlmService(
            model_capacity=ModelCapacity.LARGE,
            streaming=True,
            isolated=True,
            extended_thinking=True,
            thinking_budget_tokens=2048,
            max_attempts=0,
        )

        self.assertIsInstance(service.llm, IsolatedChatBedrock)

    def test_extended_thinking_respects_streaming_flag(self):
        """extended_thinking=True여도 streaming=True가 유지되어야 함"""
        service = AwsBedrockLlmService(
            model_capacity=ModelCapacity.LARGE,
            streaming=True,
            isolated=True,
            extended_thinking=True,
            thinking_budget_tokens=2048,
            max_attempts=0,
        )

        self.assertTrue(service.llm.streaming)

    def test_extended_thinking_injects_thinking_kwargs(self):
        """thinking budget이 model_kwargs에 정확히 주입되는지 확인"""
        budget = 2048
        service = AwsBedrockLlmService(
            model_capacity=ModelCapacity.LARGE,
            streaming=True,
            isolated=True,
            extended_thinking=True,
            thinking_budget_tokens=budget,
            max_attempts=0,
        )

        thinking = service.llm.model_kwargs.get("thinking")
        self.assertEqual(thinking, {"type": "enabled", "budget_tokens": budget})
        self.assertEqual(service.llm.temperature, 1)

    def test_extended_thinking_without_isolated_returns_plain_chat_bedrock(self):
        """isolated=False일 때는 일반 ChatBedrock 반환 (회귀 방지)"""
        service = AwsBedrockLlmService(
            model_capacity=ModelCapacity.LARGE,
            streaming=True,
            isolated=False,
            extended_thinking=True,
            thinking_budget_tokens=2048,
            max_attempts=0,
        )

        self.assertIsInstance(service.llm, ChatBedrock)
        self.assertNotIsInstance(service.llm, IsolatedChatBedrock)

    def test_non_thinking_with_isolated_returns_isolated_chat_bedrock(self):
        """기존 동작 회귀 방지: thinking 없이 isolated=True"""
        service = AwsBedrockLlmService(
            model_capacity=ModelCapacity.LARGE,
            streaming=True,
            isolated=True,
            extended_thinking=False,
            max_attempts=0,
        )

        self.assertIsInstance(service.llm, IsolatedChatBedrock)
        self.assertTrue(service.llm.streaming)
