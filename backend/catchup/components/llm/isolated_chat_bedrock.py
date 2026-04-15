from typing import Any
from typing import AsyncIterator

from langchain_aws import ChatBedrock
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.outputs import ChatResult
from langchain_core.runnables.config import run_in_executor

from catchup.rag.executors import rag_executors


class IsolatedChatBedrock(ChatBedrock):
    """LLM 전용 thread pool을 사용하는 ChatBedrock 서브클래스.

    BaseChatModel._agenerate / _astream은 run_in_executor(None, ...)로 폴백하여
    asyncio default pool을 사용한다 — ingestion blocking call과 같은 pool을 공유하게 됨.
    이 서브클래스는 두 메서드를 override하여 rag_executors.llm을 명시적으로 사용,
    ingestion이 LLM 호출 slot을 점유하지 못하도록 격리한다.

    langchain_core.run_in_executor를 그대로 사용하므로 kwargs 전달 및
    StopIteration → RuntimeError 변환 등 원본 동작과 완전히 호환된다.
    """

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return await run_in_executor(
            rag_executors.llm,
            self._generate,
            messages,
            stop,
            run_manager.get_sync() if run_manager else None,
            **kwargs,
        )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        iterator = await run_in_executor(
            rag_executors.llm,
            self._stream,
            messages,
            stop,
            run_manager.get_sync() if run_manager else None,
            **kwargs,
        )
        done = object()
        while True:
            item = await run_in_executor(
                rag_executors.llm,
                next,
                iterator,
                done,
            )
            if item is done:
                break
            yield item
