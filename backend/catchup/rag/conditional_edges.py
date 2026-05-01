import structlog

from catchup.rag.state import AgentState

logger = structlog.getLogger(__name__)


def route_after_supervisor(state: AgentState) -> str:
    """Supervisor 결정에 따라 적절한 파이프라인 서브그래프로 라우팅."""
    pipeline_plan = state.get("pipeline_plan")
    if pipeline_plan is None:
        logger.warning("supervisor_pipeline_plan_missing", fallback="standard")
        return "standard"
    return pipeline_plan.pipeline_type  # "clarify" 포함 6종
