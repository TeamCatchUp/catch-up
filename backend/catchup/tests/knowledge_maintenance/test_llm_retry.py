from __future__ import annotations

import asyncio

import pytest
import structlog
from botocore.exceptions import ClientError
from botocore.exceptions import ConnectionClosedError
from botocore.exceptions import ReadTimeoutError

from catchup.knowledge_maintenance.adapters.llm.retry import LlmRetryPolicy
from catchup.knowledge_maintenance.adapters.llm.retry import aretry_llm_call
from catchup.knowledge_maintenance.adapters.llm.retry import is_transient_llm_error
from catchup.knowledge_maintenance.adapters.llm.retry import retry_llm_call

FAST_POLICY = LlmRetryPolicy(max_attempts=3, base_delay=1.0, max_delay=8.0)


def _client_error(code: str) -> ClientError:
    """지정한 오류 코드를 담은 botocore ClientError를 만든다."""
    return ClientError(
        {"Error": {"Code": code, "Message": "boom"}},
        "InvokeModel",
    )


def test_connection_closed_is_transient() -> None:
    """응답을 다 받기 전에 끊긴 연결은 다시 걸어볼 만한 오류다."""
    assert is_transient_llm_error(ConnectionClosedError(endpoint_url="https://bedrock"))


def test_read_timeout_is_transient() -> None:
    """응답 대기 시간이 넘은 경우도 다시 걸어볼 만한 오류다."""
    assert is_transient_llm_error(ReadTimeoutError(endpoint_url="https://bedrock"))


def test_throttling_client_error_is_transient() -> None:
    """호출량 제한은 잠시 기다렸다 다시 부르면 풀린다."""
    assert is_transient_llm_error(_client_error("ThrottlingException"))


def test_validation_client_error_is_not_transient() -> None:
    """요청 자체가 잘못된 경우는 다시 불러도 같은 결과다."""
    assert not is_transient_llm_error(_client_error("ValidationException"))


def test_plain_value_error_is_not_transient() -> None:
    """일반 예외는 재시도 대상이 아니다."""
    assert not is_transient_llm_error(ValueError("bad"))


def test_sync_call_succeeds_after_two_transient_failures() -> None:
    """두 번 끊겨도 세 번째 호출이 성공하면 결과를 돌려준다."""
    calls: list[int] = []
    slept: list[float] = []

    def fn() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionClosedError(endpoint_url="https://bedrock")
        return "ok"

    result = retry_llm_call(
        fn,
        subject="unit",
        policy=FAST_POLICY,
        sleep=slept.append,
    )

    assert result == "ok"
    assert len(calls) == 3
    assert len(slept) == 2
    assert slept[0] < slept[1]


def test_async_call_succeeds_after_two_transient_failures() -> None:
    """비동기 호출도 같은 방식으로 두 번까지 다시 부른다."""
    calls: list[int] = []
    slept: list[float] = []

    async def fn() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionClosedError(endpoint_url="https://bedrock")
        return "ok"

    async def sleep(delay: float) -> None:
        slept.append(delay)

    result = asyncio.run(
        aretry_llm_call(fn, subject="unit", policy=FAST_POLICY, sleep=sleep)
    )

    assert result == "ok"
    assert len(calls) == 3
    assert len(slept) == 2
    assert slept[0] < slept[1]


def test_non_transient_error_is_raised_without_retry() -> None:
    """재시도해도 소용없는 오류는 곧바로 올린다."""
    calls: list[int] = []
    slept: list[float] = []

    def fn() -> str:
        calls.append(1)
        raise _client_error("ValidationException")

    with pytest.raises(ClientError):
        retry_llm_call(fn, subject="unit", policy=FAST_POLICY, sleep=slept.append)

    assert len(calls) == 1
    assert slept == []


def test_exhausted_retries_reraise_the_same_error() -> None:
    """정해진 횟수를 다 쓰면 마지막 예외를 그대로 올린다."""
    calls: list[int] = []
    last = ConnectionClosedError(endpoint_url="https://bedrock")

    def fn() -> str:
        calls.append(1)
        raise last

    with pytest.raises(ConnectionClosedError) as caught:
        retry_llm_call(fn, subject="unit", policy=FAST_POLICY, sleep=lambda _: None)

    assert caught.value is last
    assert len(calls) == FAST_POLICY.max_attempts


def test_retry_event_is_logged() -> None:
    """재시도 사건에 대상과 시도 번호가 남는다."""
    calls: list[int] = []

    def fn() -> str:
        calls.append(1)
        if len(calls) < 2:
            raise ConnectionClosedError(endpoint_url="https://bedrock")
        return "ok"

    with structlog.testing.capture_logs() as logs:
        retry_llm_call(fn, subject="unit", policy=FAST_POLICY, sleep=lambda _: None)

    events = [log for log in logs if log["event"] == "llm_call_retry"]
    assert len(events) == 1
    assert events[0]["subject"] == "unit"
    assert events[0]["attempt"] == 1
    assert events[0]["max_attempts"] == FAST_POLICY.max_attempts
    assert events[0]["error_type"] == "ConnectionClosedError"
    assert events[0]["delay"] > 0


def test_exhausted_event_is_logged() -> None:
    """모두 실패하면 소진 사건을 남긴다."""

    def fn() -> str:
        raise ConnectionClosedError(endpoint_url="https://bedrock")

    with structlog.testing.capture_logs() as logs:
        with pytest.raises(ConnectionClosedError):
            retry_llm_call(fn, subject="unit", policy=FAST_POLICY, sleep=lambda _: None)

    events = [log for log in logs if log["event"] == "llm_call_exhausted"]
    assert len(events) == 1
    assert events[0]["subject"] == "unit"
    assert events[0]["attempts"] == FAST_POLICY.max_attempts
    assert events[0]["error_type"] == "ConnectionClosedError"


def test_delay_grows_but_stops_at_max_delay() -> None:
    """대기 시간은 배수로 늘되 상한을 넘지 않는다."""
    policy = LlmRetryPolicy(base_delay=1.0, backoff_factor=2.0, max_delay=3.0)

    delays = [policy.delay_for(attempt, rng=lambda: 0.5) for attempt in (1, 2, 3, 4)]

    assert delays == [1.0, 2.0, 3.0, 3.0]


def test_jitter_stays_inside_the_ratio() -> None:
    """흔들림은 정해진 비율 안에서만 더하거나 뺀다."""
    policy = LlmRetryPolicy(base_delay=2.0, jitter_ratio=0.25)

    assert policy.delay_for(1, rng=lambda: 0.0) == pytest.approx(1.5)
    assert policy.delay_for(1, rng=lambda: 1.0) == pytest.approx(2.5)
