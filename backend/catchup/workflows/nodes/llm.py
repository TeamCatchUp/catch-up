from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from pydantic import BaseModel
from pydantic import Field

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.workflows.nodes.base import BaseLlm
from catchup.workflows.nodes.common.action import action
from catchup.workflows.nodes.common.types import ChatMessage
from catchup.workflows.nodes.common.types import LlmResponse

_ROLE_TO_CLS: dict[str, type[BaseMessage]] = {
    "system": SystemMessage,
    "human": HumanMessage,
    "ai": AIMessage,
}


class InvokeLlm(BaseLlm):
    class InvokeInput(BaseModel):
        messages: list[ChatMessage] = Field(
            description="LLM에 전달할 대화 메시지 목록.",
        )

    @action(
        input_model=InvokeInput,
        output_model=LlmResponse,
        description="LLM을 호출하여 메시지에 대한 응답을 생성한다.",
    )
    async def ainvoke(self, inputs: InvokeInput, node_results: dict) -> dict:
        messages: list[BaseMessage] = [
            _ROLE_TO_CLS[m.role](content=m.content)
            for m in inputs.messages
        ]
        response: AIMessage = await self._llm.ainvoke(messages)
        return {
            "content": response.content,
            "usage_metadata": response.usage_metadata,
        }

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        provider: LlmProvider,
        model_capacity: ModelCapacity,
    ):
        super().__init__(name, display_name, description)
        self._llm = get_llm_service(
            provider=provider,
            model_capacity=model_capacity,
            streaming=False,
        ).get_llm()
