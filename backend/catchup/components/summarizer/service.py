"""
Summarizer Service for embedding-optimized text generation.

문서를 소스 타입별 프롬프트로 요약하여 검색에 최적화된 자연어 텍스트를 생성합니다.
사람 이름, 관계, 맥락을 보존하면서 형식적 구조를 제거합니다.
"""

import asyncio
from dataclasses import dataclass

from openai import AsyncOpenAI

from catchup.components.summarizer.prompts import get_summary_prompt
from catchup.configs.config import settings


@dataclass
class SummarizeRequest:
    """요약 요청 DTO."""

    content: str
    source_type: str


class SummarizerService:
    """
    OpenAI GPT-4o-mini를 사용한 문서 요약 서비스.

    소스 타입별 특화된 프롬프트로 검색 최적화 요약을 생성합니다.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_tokens: int = 300,
        temperature: float = 0.3,
    ):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def summarize(self, content: str, source_type: str) -> str:
        """
        단일 문서를 소스 타입에 맞게 요약합니다.

        Args:
            content: 요약할 원본 텍스트
            source_type: 문서 소스 타입 (github_issue, slack_message 등)

        Returns:
            요약된 텍스트. 실패 시 원본 반환.
        """
        if not content or not content.strip():
            return content

        # 너무 짧은 내용은 요약 불필요
        if len(content) < 100:
            return content

        try:
            system_prompt, user_prompt = get_summary_prompt(source_type, content)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            summary = response.choices[0].message.content
            return summary.strip() if summary else content

        except Exception as e:
            # 요약 실패 시 원본 반환 (임베딩은 계속 진행)
            print(f"[SummarizerService] Summarization failed: {e}")
            return content

    async def summarize_batch(
        self,
        requests: list[SummarizeRequest],
        max_concurrent: int = 10,
    ) -> list[str]:
        """
        여러 문서를 병렬로 요약합니다.

        Args:
            requests: 요약 요청 리스트 (content + source_type)
            max_concurrent: 최대 동시 요청 수

        Returns:
            요약된 텍스트 리스트 (순서 유지)
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _summarize_with_semaphore(req: SummarizeRequest) -> str:
            async with semaphore:
                return await self.summarize(req.content, req.source_type)

        tasks = [_summarize_with_semaphore(req) for req in requests]
        return await asyncio.gather(*tasks)
