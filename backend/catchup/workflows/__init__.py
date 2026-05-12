from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.workflows.graph.compiler import WorkflowCompileError
from catchup.workflows.graph.compiler import WorkflowState
from catchup.workflows.graph.compiler import compile_workflow
from catchup.workflows.nodes.common.registry import NodeRegistry
from catchup.workflows.nodes.llm import InvokeLlm


def init_workflow_node_registry() -> None:
    NodeRegistry.register(
        InvokeLlm(
            name="invoke_llm_small",
            display_name="Invoke LLM (Small)",
            description="소형 LLM을 호출하여 텍스트 응답을 반환한다.",
            provider=LlmProvider.AWS_BEDROCK,
            model_capacity=ModelCapacity.SMALL,
        )
    )
    NodeRegistry.register(
        InvokeLlm(
            name="invoke_llm_large",
            display_name="Invoke LLM (Large)",
            description="대형 LLM을 호출하여 텍스트 응답을 반환한다.",
            provider=LlmProvider.AWS_BEDROCK,
            model_capacity=ModelCapacity.LARGE,
        )
    )
