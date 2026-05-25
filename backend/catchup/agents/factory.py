from functools import lru_cache

from catchup.agents.engine import ExecutionService
from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.factory import get_llm_service
from catchup.components.llm.service import ModelCapacity


@lru_cache(maxsize=1)
def get_execution_service() -> ExecutionService:
    llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=False,
        isolated=True,
    ).get_llm()
    return ExecutionService(llm=llm)
