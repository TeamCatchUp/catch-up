import asyncio

from botocore.exceptions import ConnectionClosedError as BotocoreConnectionClosedError

# LangGraph RetryPolicy에서 재시도할 예외 목록.
# 노드의 except 블록에서 이 타입들은 반드시 re-raise해야 RetryPolicy가 트리거된다.
RETRYABLE_ERRORS = (asyncio.TimeoutError, BotocoreConnectionClosedError)
