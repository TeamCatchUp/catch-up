from __future__ import annotations

import asyncio
import functools
import time
from typing import Any
from typing import Awaitable
from typing import Callable

import structlog
from langchain_core.messages import BaseMessage

from catchup.costs.utils import extract_token_usages

logger = structlog.get_logger("catchup.graph")


async def ainvoke_llm_with_token_usage(
    llm: Any,
    messages: list[BaseMessage],
    semaphore: Any = None,
    timeout: float | None = None,
    **kwargs: Any,
) -> tuple[Any, dict]:
    """LLM을 호출하고 토큰 사용량을 추출한다. 에러 발생 시 예외를 전파한다."""
    token_usages = {"token_breakdown": {}}
    try:
        async with asyncio.timeout(timeout):
            if semaphore:
                t_sem = time.perf_counter()
                logger.debug(
                    "semaphore_acquiring",
                    semaphore=semaphore.name,
                )
                async with semaphore:
                    t_llm = time.perf_counter()
                    logger.debug(
                        "llm_invoke_start",
                        semaphore_wait_elapsed=round(t_llm - t_sem, 3),
                    )
                    response = await llm.ainvoke(input=messages, **kwargs)
            else:
                t_llm = time.perf_counter()
                logger.debug("llm_invoke_without_semaphore_start")
                response = await llm.ainvoke(input=messages, **kwargs)

        logger.debug(
            "llm_invoke_completed", elapsed=round(time.perf_counter() - t_llm, 3)
        )

        # response가 dict인 경우 (with_structured_output include_raw=True) 처리
        raw_response = response.get("raw") if isinstance(response, dict) else response
        token_usages = extract_token_usages(raw_response)
        return response, token_usages

    except asyncio.TimeoutError as e:
        logger.warning(
            "llm_call_timeout",
            timeout=timeout,
            error=str(e),
            exc_info=True,
        )
        raise e
    except Exception as e:
        logger.warning("llm_call_failed", error=str(e), exc_info=True)
        raise e


def log_node(func: Callable[..., Awaitable[dict]]):
    """LangGraph 노드 실행 전후로 로깅을 수행하는 데코레이터."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        node_name = func.__name__
        start_time = time.perf_counter()
        logger.info("node_started", node_name=node_name)
        try:
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            logger.info(
                "node_completed", node_name=node_name, duration=round(elapsed, 4)
            )
            return result
        except Exception as e:
            logger.error(
                "node_failed", node_name=node_name, error=str(e), exc_info=True
            )
            raise e

    return wrapper
