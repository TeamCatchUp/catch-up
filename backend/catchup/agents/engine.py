import structlog
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from catchup.agents.harness.graph import build_execution_graph
from catchup.agents.harness.graph import run_execution_agent
from catchup.agents.schemas import AgentSpec
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.configs.config import settings
from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.langfuse.configs import get_observe

logger = structlog.get_logger()
observe = get_observe()


class ExecutionService:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm
        # agent_specs.id → CompiledStateGraph
        # DB row PK를 키로 사용해 spec 버전이 바뀌면 다른 키로 캐싱된다.
        self._graph_cache: dict[int, CompiledStateGraph] = {}

        if settings.ENABLE_LANGFUSE:
            logger.info("langfuse_initialized", context="execution_service", active=True)

    def _get_graph(self, spec_id: int, spec: AgentSpec) -> CompiledStateGraph:
        """spec_id 기준으로 컴파일된 그래프를 캐싱해 반환한다."""
        if spec_id not in self._graph_cache:
            self._graph_cache[spec_id] = build_execution_graph(spec, self._llm)
        return self._graph_cache[spec_id]

    def _build_invoke_config(self) -> dict:
        """Langfuse CallbackHandler를 주입한 invoke config를 반환한다."""
        config: dict = {"recursion_limit": 50}
        if settings.ENABLE_LANGFUSE:
            if client := get_langfuse_client():
                from langfuse.langchain import CallbackHandler
                trace_id = client.get_current_trace_id()
                config["callbacks"] = [
                    CallbackHandler(trace_context={"trace_id": trace_id})
                ]
        return config

    @observe(name="execution-agent")
    async def run(
        self,
        spec_id: int,
        spec: AgentSpec,
        user_input_values: dict,
        trigger_event: AgentWebhookEvent,
    ) -> str:
        """Execution Agent를 실행하고 최종 응답 텍스트를 반환한다."""
        result = await run_execution_agent(
            spec=spec,
            user_input_values=user_input_values,
            trigger_event=trigger_event,
            graph=self._get_graph(spec_id, spec),
            invoke_config=self._build_invoke_config(),
        )

        if settings.ENABLE_LANGFUSE:
            if client := get_langfuse_client():
                from fastapi.concurrency import run_in_threadpool
                await run_in_threadpool(client.flush)

        return result
