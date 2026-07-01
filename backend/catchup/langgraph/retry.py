import asyncio

from botocore.exceptions import ConnectionClosedError as BotocoreConnectionClosedError
from langgraph.types import RetryPolicy

# LangGraph RetryPolicy에서 재시도할 예외 목록.
# 노드의 except 블록에서 이 타입들은 반드시 re-raise해야 RetryPolicy가 트리거된다.
RETRYABLE_ERRORS = (asyncio.TimeoutError, BotocoreConnectionClosedError)

# 기본 재시도 정책
# max_attempt는 최초 시도 횟수를 포함.
BASE_RETRY_POLICY = RetryPolicy(
    retry_on=RETRYABLE_ERRORS,
    max_attempts=3,
    initial_interval=1.0,
    backoff_factor=2.0,
)

# Agent는 내부 루프가 길어 재시도 횟수를 제한
AGENT_RETRY_POLICY = RetryPolicy(
    retry_on=RETRYABLE_ERRORS,
    max_attempts=2,
    initial_interval=1.0,
    backoff_factor=2.0,
)
