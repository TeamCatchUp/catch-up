"""
Summarizer Service for embedding-optimized text generation.

문서를 소스 타입별 프롬프트로 요약하여 검색에 최적화된 자연어 텍스트를 생성합니다.
사람 이름, 관계, 맥락을 보존하면서 형식적 구조를 제거합니다.
"""

import asyncio
import logging
import random
import time
from collections import deque
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass

from botocore.exceptions import ClientError
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.components.summarizer.prompts import get_summary_prompt
from catchup.configs.config import settings
from catchup.connectors.base.retry import parse_retry_after_header
from catchup.events.enums import SyncIngestionEventAction
from catchup.sync.audit import SyncAuditContext
from catchup.sync.audit import emit_sync_ingestion_audit

logger = logging.getLogger(__name__)

SUMMARIZER_MAX_ATTEMPTS = 3
SUMMARIZER_MAX_RETRY_DELAY_SECONDS = 60
SUMMARIZER_BACKOFF_BASE_SECONDS = 1.0
SUMMARIZER_BACKOFF_JITTER_RATIO = 0.2
BEDROCK_THROTTLING_ERROR_CODE = "ThrottlingException"


class SummarizerRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ):
        self.limit = max(1, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._starts: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            wait_seconds = 0.0

            async with self._lock:
                now = self._clock()
                self._prune(now)

                if len(self._starts) < self.limit:
                    self._starts.append(now)
                    return

                oldest = self._starts[0]
                wait_seconds = max(0.0, self.window_seconds - (now - oldest))

            await self._sleep(wait_seconds)

    def _prune(self, now: float) -> None:
        while self._starts and now - self._starts[0] >= self.window_seconds:
            self._starts.popleft()


@dataclass
class SummarizeRequest:
    """요약 요청 DTO."""

    content: str
    source_type: str


@dataclass(frozen=True)
class SummarizerRetryDelay:
    seconds: float
    source: str


@dataclass(frozen=True)
class SummarizerRetryPolicy:
    max_attempts: int = SUMMARIZER_MAX_ATTEMPTS
    max_delay_seconds: int = SUMMARIZER_MAX_RETRY_DELAY_SECONDS
    base_delay_seconds: float = SUMMARIZER_BACKOFF_BASE_SECONDS
    jitter_ratio: float = SUMMARIZER_BACKOFF_JITTER_RATIO

    def resolve_delay(
        self,
        *,
        attempt: int,
        retry_after: int | None,
        random_value: float,
    ) -> SummarizerRetryDelay:
        if retry_after is not None:
            return SummarizerRetryDelay(
                seconds=min(retry_after, self.max_delay_seconds),
                source="retry-after",
            )

        base_delay = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (2 ** max(0, attempt - 1)),
        )
        jitter = base_delay * self.jitter_ratio * random_value
        return SummarizerRetryDelay(
            seconds=min(self.max_delay_seconds, base_delay + jitter),
            source="exponential-backoff",
        )


class SummarizerService:
    def __init__(
        self,
        max_tokens: int = 300,
        temperature: float = 0.3,
        model_capacity: ModelCapacity = ModelCapacity.SMALL,
        llm: BaseChatModel | None = None,
        rate_limiter: SummarizerRateLimiter | None = None,
        retry_policy: SummarizerRetryPolicy | None = None,
        retry_sleep: Callable[[float], Awaitable[None]] | None = None,
        retry_random: Callable[[], float] | None = None,
    ):
        base_llm = llm or get_llm_service(
            provider=LlmProvider.AWS_BEDROCK,
            model_capacity=model_capacity,
            streaming=False,
            max_attempts=5,
        ).get_llm()
        self.llm = base_llm.bind(
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.rate_limiter = rate_limiter or SummarizerRateLimiter(
            limit=settings.AWS_BEDROCK_SMALL_RPM,
            window_seconds=60,
        )
        self.retry_policy = retry_policy or SummarizerRetryPolicy()
        self._retry_sleep = retry_sleep or asyncio.sleep
        self._retry_random = retry_random or random.random

    async def summarize(self, content: str, source_type: str) -> str:
        """
        단일 문서를 소스 타입에 맞게 요약합니다.

        Args:
            content: 요약할 원본 텍스트
            source_type: 문서 소스 타입 (github_issue, slack_message 등)

        Returns:
            요약된 텍스트.
        """
        if self._should_skip_summarization(content):
            return content

        messages = self._build_summary_messages(content, source_type)
        response = await self._invoke_with_bedrock_throttling_retry(messages)
        return self._extract_summary(response.content, fallback=content)

    def _should_skip_summarization(self, content: str) -> bool:
        return not content or not content.strip() or len(content) < 100

    def _build_summary_messages(
        self,
        content: str,
        source_type: str,
    ) -> list[BaseMessage]:
        system_prompt, user_prompt = get_summary_prompt(source_type, content)
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

    def _extract_summary(self, summary: object, *, fallback: str) -> str:
        if isinstance(summary, str):
            return summary.strip() or fallback
        if isinstance(summary, list) and summary:
            first_piece = summary[0]
            if isinstance(first_piece, dict) and "text" in first_piece:
                return (first_piece["text"] or fallback).strip()
            if isinstance(first_piece, str):
                return first_piece.strip() or fallback
        return fallback

    async def _invoke_with_bedrock_throttling_retry(
        self,
        messages: list[BaseMessage],
    ) -> object:
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            await self.rate_limiter.acquire()
            try:
                return await self.llm.ainvoke(messages)
            except Exception as exc:
                if (
                    attempt >= self.retry_policy.max_attempts
                    or not _is_bedrock_throttling_error(exc)
                ):
                    raise

                retry_after = _extract_bedrock_retry_after_seconds(exc)
                delay = self.retry_policy.resolve_delay(
                    attempt=attempt,
                    retry_after=retry_after,
                    random_value=self._retry_random(),
                )
                self._log_bedrock_retry(attempt=attempt, delay=delay, error=exc)
                await self._retry_sleep(delay.seconds)

        raise RuntimeError("unreachable summarizer retry state")

    def _log_bedrock_retry(
        self,
        *,
        attempt: int,
        delay: SummarizerRetryDelay,
        error: Exception,
    ) -> None:
        logger.warning(
            "[SummarizerService] Bedrock throttled. Retrying: "
            "attempt=%s/%s, delay=%ss, retry_after_source=%s, error=%s",
            attempt,
            self.retry_policy.max_attempts,
            delay.seconds,
            delay.source,
            error.__class__.__name__,
        )

    async def summarize_batch(
        self,
        requests: list[SummarizeRequest],
        max_concurrent: int = 50,
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


def _is_bedrock_throttling_error(error: Exception) -> bool:
    for exc in _iter_exception_chain(error):
        if _is_throttled_client_error(exc):
            return True
        if _has_throttling_text(exc):
            return True
    return False


def _extract_bedrock_retry_after_seconds(error: Exception) -> int | None:
    for exc in _iter_exception_chain(error):
        if not isinstance(exc, ClientError):
            continue

        headers = _client_error_headers(exc)
        retry_after = _get_case_insensitive_header(headers, "retry-after")
        if retry_after is None:
            continue

        return parse_retry_after_header(
            retry_after,
            default=int(SUMMARIZER_BACKOFF_BASE_SECONDS),
        )

    return None


def _is_throttled_client_error(error: BaseException) -> bool:
    if not isinstance(error, ClientError):
        return False

    response = error.response or {}
    error_code = response.get("Error", {}).get("Code")
    return error_code == BEDROCK_THROTTLING_ERROR_CODE


def _has_throttling_text(error: BaseException) -> bool:
    if error.__class__.__name__ == BEDROCK_THROTTLING_ERROR_CODE:
        return True

    return BEDROCK_THROTTLING_ERROR_CODE in str(error)


def _client_error_headers(error: ClientError) -> dict[str, object]:
    return (
        (error.response or {})
        .get("ResponseMetadata", {})
        .get("HTTPHeaders", {})
    )


def _iter_exception_chain(error: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = error

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _get_case_insensitive_header(
    headers: dict[str, object],
    name: str,
) -> str | None:
    normalized = name.lower()
    for key, value in headers.items():
        if str(key).lower() == normalized and value is not None:
            return str(value)
    return None
