from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from botocore.exceptions import ClientError

from catchup.audit.enums import AuditEventStatus
from catchup.components.summarizer.service import SummarizeRequest
from catchup.components.summarizer.service import SummarizerService


class FakeLlm:
    def __init__(self, results: list[object]):
        self.results = list(results)
        self.calls = 0

    def bind(self, **_kwargs):
        return self

    async def ainvoke(self, _messages):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeRateLimiter:
    def __init__(self):
        self.calls = 0

    async def acquire(self) -> None:
        self.calls += 1


class SleepRecorder:
    def __init__(self):
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _long_content() -> str:
    return "요약 대상 본문입니다. " * 20


def _response(content: str):
    return SimpleNamespace(content=content)


def _throttling_error(
    *,
    retry_after: str | None = None,
    status_code: int = 429,
) -> ClientError:
    headers = {}
    if retry_after is not None:
        headers["retry-after"] = retry_after

    return ClientError(
        {
            "Error": {
                "Code": "ThrottlingException",
                "Message": "Too many requests",
            },
            "ResponseMetadata": {
                "HTTPStatusCode": status_code,
                "HTTPHeaders": headers,
            },
        },
        "InvokeModel",
    )


def _client_error(
    *,
    code: str,
    message: str = "upstream failed",
    status_code: int = 500,
) -> ClientError:
    return ClientError(
        {
            "Error": {
                "Code": code,
                "Message": message,
            },
            "ResponseMetadata": {
                "HTTPStatusCode": status_code,
                "HTTPHeaders": {},
            },
        },
        "InvokeModel",
    )


class TestSummarizerServiceRetry(IsolatedAsyncioTestCase):
    async def test_default_bedrock_llm_uses_botocore_retries(self) -> None:
        fake_service = SimpleNamespace(get_llm=lambda: FakeLlm([_response("unused")]))

        with patch(
            "catchup.components.summarizer.service.get_llm_service",
            return_value=fake_service,
        ) as get_llm_service:
            SummarizerService()

        self.assertEqual(get_llm_service.call_args.kwargs["max_attempts"], 5)

    async def test_retry_after_header_controls_retry_delay(self) -> None:
        sleep = SleepRecorder()
        llm = FakeLlm([_throttling_error(retry_after="37"), _response("summary")])
        rate_limiter = FakeRateLimiter()
        service = SummarizerService(
            llm=llm,
            rate_limiter=rate_limiter,
            retry_sleep=sleep,
        )

        result = await service.summarize(_long_content(), "jira_issue")

        self.assertEqual(result, "summary")
        self.assertEqual(sleep.delays, [37])
        self.assertEqual(llm.calls, 2)
        self.assertEqual(rate_limiter.calls, 2)

    async def test_retry_after_delay_is_capped(self) -> None:
        sleep = SleepRecorder()
        llm = FakeLlm([_throttling_error(retry_after="120"), _response("summary")])
        service = SummarizerService(
            llm=llm,
            rate_limiter=FakeRateLimiter(),
            retry_sleep=sleep,
        )

        result = await service.summarize(_long_content(), "jira_issue")

        self.assertEqual(result, "summary")
        self.assertEqual(sleep.delays, [60])

    async def test_wrapped_throttling_error_uses_cause_retry_after(self) -> None:
        sleep = SleepRecorder()
        wrapped = RuntimeError("langchain wrapper")
        wrapped.__cause__ = _throttling_error(retry_after="5")
        llm = FakeLlm([wrapped, _response("summary")])
        service = SummarizerService(
            llm=llm,
            rate_limiter=FakeRateLimiter(),
            retry_sleep=sleep,
        )

        result = await service.summarize(_long_content(), "jira_issue")

        self.assertEqual(result, "summary")
        self.assertEqual(sleep.delays, [5])

    async def test_missing_retry_after_uses_exponential_backoff(self) -> None:
        sleep = SleepRecorder()
        llm = FakeLlm(
            [
                _throttling_error(),
                _throttling_error(),
                _response("summary"),
            ]
        )
        service = SummarizerService(
            llm=llm,
            rate_limiter=FakeRateLimiter(),
            retry_sleep=sleep,
            retry_random=lambda: 0.0,
        )

        result = await service.summarize(_long_content(), "jira_issue")

        self.assertEqual(result, "summary")
        self.assertEqual(sleep.delays, [1.0, 2.0])

    async def test_final_throttling_failure_is_raised(self) -> None:
        sleep = SleepRecorder()
        llm = FakeLlm(
            [
                _throttling_error(),
                _throttling_error(),
                _throttling_error(),
            ]
        )
        service = SummarizerService(
            llm=llm,
            rate_limiter=FakeRateLimiter(),
            retry_sleep=sleep,
            retry_random=lambda: 0.0,
        )

        with self.assertRaises(ClientError):
            await service.summarize(_long_content(), "jira_issue")

        self.assertEqual(sleep.delays, [1.0, 2.0])
        self.assertEqual(llm.calls, 3)

    async def test_non_throttling_client_error_is_not_retried(self) -> None:
        sleep = SleepRecorder()
        llm = FakeLlm([_client_error(code="ValidationException", status_code=400)])
        service = SummarizerService(
            llm=llm,
            rate_limiter=FakeRateLimiter(),
            retry_sleep=sleep,
        )

        with self.assertRaises(ClientError):
            await service.summarize(_long_content(), "jira_issue")

        self.assertEqual(sleep.delays, [])
        self.assertEqual(llm.calls, 1)

    async def test_other_bedrock_429_error_is_not_retried(self) -> None:
        sleep = SleepRecorder()
        llm = FakeLlm([_client_error(code="ModelNotReadyException", status_code=429)])
        service = SummarizerService(
            llm=llm,
            rate_limiter=FakeRateLimiter(),
            retry_sleep=sleep,
        )

        with self.assertRaises(ClientError):
            await service.summarize(_long_content(), "jira_issue")

        self.assertEqual(sleep.delays, [])
        self.assertEqual(llm.calls, 1)

    async def test_short_or_empty_content_skips_llm(self) -> None:
        llm = FakeLlm([_response("unused")])
        service = SummarizerService(llm=llm, rate_limiter=FakeRateLimiter())

        self.assertEqual(await service.summarize("", "jira_issue"), "")
        self.assertEqual(await service.summarize("short", "jira_issue"), "short")
        self.assertEqual(llm.calls, 0)

    async def test_batch_failure_raises_and_emits_fail_audit(self) -> None:
        sleep = SleepRecorder()
        llm = FakeLlm(
            [
                _throttling_error(),
                _throttling_error(),
                _throttling_error(),
            ]
        )
        service = SummarizerService(
            llm=llm,
            rate_limiter=FakeRateLimiter(),
            retry_sleep=sleep,
            retry_random=lambda: 0.0,
        )
        emitted_statuses: list[AuditEventStatus] = []

        def capture_audit(**kwargs):
            emitted_statuses.append(kwargs["status"])

        with patch(
            "catchup.components.summarizer.service.emit_sync_ingestion_audit",
            side_effect=capture_audit,
        ):
            with self.assertRaises(ClientError):
                await service.summarize_batch(
                    [SummarizeRequest(content=_long_content(), source_type="jira_issue")],
                    max_concurrent=1,
                    audit_context=object(),
                    context="test",
                )

        self.assertEqual(
            emitted_statuses,
            [AuditEventStatus.ATTEMPT, AuditEventStatus.FAIL],
        )
        self.assertEqual(sleep.delays, [1.0, 2.0])

    async def test_batch_success_preserves_order(self) -> None:
        llm = FakeLlm([_response("first"), _response("second")])
        service = SummarizerService(llm=llm, rate_limiter=FakeRateLimiter())

        result = await service.summarize_batch(
            [
                SummarizeRequest(content=_long_content(), source_type="jira_issue"),
                SummarizeRequest(content=_long_content(), source_type="jira_issue"),
            ],
            max_concurrent=1,
        )

        self.assertEqual(result, ["first", "second"])
