"""LLM과 임베딩 호출을 일시적 오류에서 다시 부르는 재시도 도구를 담는다.

botocore가 자체로 가진 재시도(`retries={"max_attempts": 5, "mode": "standard"}`)는
요청을 보내는 구간만 덮는다. 응답 본문을 읽는 도중 연결이 끊기는
`ConnectionClosedError`는 그 재시도에 걸리지 않아, 호출 단위로 한 겹 더
감싸야 한다. knowledge_maintenance 파이프라인은 LangGraph를 쓰지 않으므로
`catchup/langgraph/retry.py`의 RetryPolicy가 대신 잡아 주지도 않는다.

최악의 경우 호출 수는 다음과 같다. 이 래퍼가 3회, 그 안에서 botocore가 5회를
쓰므로 호출 한 번당 HTTP 시도는 최대 15회다. block_narrator는 계약 파싱
실패 시 모델을 2번 부르므로 모델 호출은 최대 6회, HTTP 시도는 최대 30회다.
vocabulary_converger도 MAX_ATTEMPTS가 2라 같은 계산이 나온다.

프롬프트와 응답 본문은 어떤 경우에도 로그에 남기지 않는다.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from botocore.exceptions import ClientError
from botocore.exceptions import ConnectionClosedError
from botocore.exceptions import ConnectTimeoutError
from botocore.exceptions import EndpointConnectionError
from botocore.exceptions import ReadTimeoutError

from catchup.observability.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

TRANSIENT_ERROR_TYPES: tuple[type[BaseException], ...] = (
    TimeoutError,
    ReadTimeoutError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ConnectionClosedError,
)

TRANSIENT_ERROR_CODES: frozenset[str] = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "ModelTimeoutException",
        "InternalServerException",
    }
)


@dataclass(frozen=True, slots=True)
class LlmRetryPolicy:
    """다시 부를 횟수와 기다릴 시간을 정한다.

    Attributes:
        max_attempts: 첫 호출을 포함해 시도할 최대 횟수를 나타낸다.
        base_delay: 첫 재시도 전에 기다릴 초를 나타낸다.
        backoff_factor: 시도마다 대기 시간을 곱할 배수를 나타낸다.
        max_delay: 한 번에 기다릴 수 있는 최대 초를 나타낸다.
        jitter_ratio: 대기 시간을 흔들 비율을 나타낸다. 여러 호출이 같은
            순간에 몰려 다시 몰리는 일을 막는다.
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 8.0
    jitter_ratio: float = 0.25

    def delay_for(
        self,
        attempt: int,
        rng: Callable[[], float] = random.random,
    ) -> float:
        """`attempt`번째 시도가 실패한 뒤 기다릴 초를 계산한다.

        Args:
            attempt: 방금 실패한 시도 번호를 받는다. 1부터 센다.
            rng: 0과 1 사이 난수를 주는 함수를 받는다. 시험에서 흔들림을
                고정하려고 바꿔 넣는다.
        """
        base = min(
            self.max_delay,
            self.base_delay * self.backoff_factor ** (attempt - 1),
        )
        jitter = base * self.jitter_ratio * (2.0 * rng() - 1.0)
        return max(0.0, base + jitter)


DEFAULT_LLM_RETRY_POLICY = LlmRetryPolicy()


def is_transient_llm_error(error: BaseException) -> bool:
    """다시 불러 볼 만한 오류인지 판단한다.

    연결이 끊겼거나 시간이 넘었거나 호출량 제한에 걸린 경우만 참이다.
    요청 자체가 잘못된 경우와 권한 문제는 다시 불러도 같은 결과라 거짓이다.
    """
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code")
        return code in TRANSIENT_ERROR_CODES
    return isinstance(error, TRANSIENT_ERROR_TYPES)


def _delay_before_retry(
    error: BaseException,
    attempt: int,
    *,
    subject: str,
    policy: LlmRetryPolicy,
) -> float | None:
    """다시 부를지 판단하고, 부른다면 기다릴 초를 돌려준다.

    다시 부르지 않기로 하면 None을 돌려준다. 부르는 쪽은 잡은 예외를 그대로
    다시 올린다. 재시도 대상이 아닌 오류에는 아무 사건도 남기지 않는다.
    이미 호출부가 자기 실패 사건을 남기기 때문이다.
    """
    if not is_transient_llm_error(error):
        return None
    if attempt >= policy.max_attempts:
        logger.warning(
            "llm_call_exhausted",
            subject=subject,
            attempts=attempt,
            error_type=type(error).__name__,
        )
        return None
    delay = policy.delay_for(attempt)
    logger.warning(
        "llm_call_retry",
        subject=subject,
        attempt=attempt,
        max_attempts=policy.max_attempts,
        error_type=type(error).__name__,
        delay=round(delay, 3),
    )
    return delay


def retry_llm_call(
    fn: Callable[[], T],
    *,
    subject: str,
    policy: LlmRetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """동기 호출을 일시적 오류에서 다시 부른다.

    Args:
        fn: 인자 없이 부를 수 있게 감싼 호출을 받는다.
        subject: 로그에 남길 호출 대상 이름을 받는다.
        policy: 재시도 규칙을 받는다. 주지 않으면 모듈 기본값을 쓴다.
        sleep: 기다리는 함수를 받는다. 시험에서 바꿔 넣는다.

    Returns:
        `fn`이 성공했을 때의 결과를 그대로 돌려준다.

    Raises:
        BaseException: 재시도 대상이 아니거나 횟수를 다 썼을 때, 마지막
            예외를 그대로 다시 올린다.
    """
    active = policy or DEFAULT_LLM_RETRY_POLICY
    attempt = 1
    while True:
        try:
            return fn()
        except Exception as error:
            delay = _delay_before_retry(error, attempt, subject=subject, policy=active)
            if delay is None:
                raise
        sleep(delay)
        attempt += 1


async def aretry_llm_call(
    fn: Callable[[], Awaitable[T]],
    *,
    subject: str,
    policy: LlmRetryPolicy | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """비동기 호출을 일시적 오류에서 다시 부른다.

    판단 규칙과 로그는 `retry_llm_call`과 같다. 기다리는 동안 이벤트 루프를
    막지 않으려고 `asyncio.sleep`을 쓴다.

    Args:
        fn: 부를 때마다 새 코루틴을 만드는 함수를 받는다. 한 번 만든
            코루틴은 다시 await할 수 없어, 코루틴이 아니라 그것을 만드는
            함수를 받아야 한다.
        subject: 로그에 남길 호출 대상 이름을 받는다.
        policy: 재시도 규칙을 받는다. 주지 않으면 모듈 기본값을 쓴다.
        sleep: 기다리는 코루틴 함수를 받는다. 시험에서 바꿔 넣는다.

    Returns:
        `fn`이 성공했을 때의 결과를 그대로 돌려준다.

    Raises:
        BaseException: 재시도 대상이 아니거나 횟수를 다 썼을 때, 마지막
            예외를 그대로 다시 올린다.
    """
    active = policy or DEFAULT_LLM_RETRY_POLICY
    attempt = 1
    while True:
        try:
            return await fn()
        except Exception as error:
            delay = _delay_before_retry(error, attempt, subject=subject, policy=active)
            if delay is None:
                raise
        await sleep(delay)
        attempt += 1
