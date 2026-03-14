"""
Summarizer Service for embedding-optimized text generation.

문서를 소스 타입별 프롬프트로 요약하여 검색에 최적화된 자연어 텍스트를 생성합니다.
사람 이름, 관계, 맥락을 보존하면서 형식적 구조를 제거합니다.
"""

import asyncio
import logging
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from numpy import isin

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.components.llm.constants import LlmProvider, ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.components.summarizer.prompts import get_summary_prompt
from catchup.configs.config import settings
from catchup.sync.audit import SyncAuditContext, emit_sync_ingestion_audit
from catchup.events.enums import SyncIngestionEventAction

logger = logging.getLogger(__name__)

@dataclass
class SummarizeRequest:
    """요약 요청 DTO."""

    content: str
    source_type: str


class SummarizerService:

    def __init__(
        self,
        max_tokens: int = 300,
        temperature: float = 0.3,
        model_capacity: ModelCapacity = ModelCapacity.SMALL,
    ):
        base_llm = get_llm_service(
            provider = LlmProvider.AWS_BEDROCK,
            model_capacity = model_capacity,
        ).get_llm()
        self.llm = base_llm.bind(
            temperature = temperature,
            max_tokens = max_tokens,
        )
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

            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )

            summary = response.content
            if isinstance(summary, str):
                return summary.strip() or content
            if isinstance(summary, list) and summary:
                first_piece = summary[0]
                if isinstance(first_piece, dict) and "text" in first_piece:
                    return (first_piece["text"] or content).strip()
                if isinstance(first_piece, str):
                    return first_piece.strip() or content
            
            return content
                

        except Exception as e:
            # 요약 실패 시 원본 반환 (임베딩은 계속 진행)
            print(f"[SummarizerService] Summarization failed: {e}")
            return content

    async def summarize_batch(
        self,
        requests: list[SummarizeRequest],
        max_concurrent: int = 25,
        audit_context: SyncAuditContext | None = None,
        context: str | None = None,
    ) -> list[str]:
        """
        여러 문서를 병렬로 요약합니다.

        Args:
            requests: 요약 요청 리스트 (content + source_type)
            max_concurrent: 최대 동시 요청 수

        Returns:
            요약된 텍스트 리스트 (순서 유지)
        """
        if audit_context is not None:
            emit_sync_ingestion_audit(
                action=SyncIngestionEventAction.SUMMARIZE,
                status=AuditEventStatus.ATTEMPT,
                audit_context=audit_context,
                context=context,
            )

        semaphore = asyncio.Semaphore(max_concurrent)

        async def _summarize_with_semaphore(req: SummarizeRequest) -> str:
            async with semaphore:
                return await self.summarize(req.content, req.source_type)

        tasks = [_summarize_with_semaphore(req) for req in requests]
        try:
            summarized = await asyncio.gather(*tasks)
        except Exception as exc:
            if audit_context is not None:
                emit_sync_ingestion_audit(
                    action=SyncIngestionEventAction.SUMMARIZE,
                    status=AuditEventStatus.FAIL,
                    audit_context=audit_context,
                    context=(
                        f"{context},error={_truncate_error(exc)}"
                        if context
                        else f"error={_truncate_error(exc)}"
                    ),
                    level=AuditLevel.ERROR,
                )
            raise

        if audit_context is not None:
            emit_sync_ingestion_audit(
                action=SyncIngestionEventAction.SUMMARIZE,
                status=AuditEventStatus.SUCCESS,
                audit_context=audit_context,
                context=context,
            )
        return summarized


def _truncate_error(error: Exception) -> str:
    return str(error).strip()[:200] or error.__class__.__name__
