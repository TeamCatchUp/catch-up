import inspect
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class ActionSpec:
    """액션의 입출력 스키마와 설명을 담는 메타데이터."""
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    description: str = ""


def action(
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    description: str = "",
) -> Callable:
    """
    액션 메서드에 입출력 스키마를 선언하는 데코레이터.

    @action(
        input_model=SendMessageInput,
        output_model=SendMessageOutput,
        description="Slack 채널에 메시지를 전송한다.",
    )
    async def send_message(self, inputs: SendMessageInput, context: dict) -> dict:
        ...
    """
    def decorator(func: Callable) -> Callable:
        func.__action_spec__ = ActionSpec(
            input_model=input_model,
            output_model=output_model,
            description=description,
        )
        return func
    return decorator


def get_action_specs(obj: object) -> dict[str, ActionSpec]:
    """인스턴스의 모든 액션 스펙을 반환한다."""
    specs = {}
    for attr_name, method in inspect.getmembers(obj, predicate=inspect.ismethod):
        spec = getattr(method.__func__, "__action_spec__", None)
        if spec is not None:
            specs[attr_name] = spec
    return specs
