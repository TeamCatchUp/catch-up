import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import HumanMessage

from catchup.costs.utils import token_usage
from catchup.langgraph.retry import RETRYABLE_ERRORS
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.state import AgentState
from catchup.schemas.sources import SOURCE_METADATA
from catchup.schemas.structures import PipelinePlan
from catchup.utils.semaphores import service_semaphores

logger = structlog.get_logger()

_PIPELINE_ORDER = ["clarify", "direct_answer", "simple", "standard", "complex"]
_DEFAULT_MAX_ITERATIONS: dict[str, int] = {
    "direct_answer": 0,
    "simple": 0,
    "standard": 4,
    "complex": 8,
}


@log_node
@token_usage
async def supervisor_node(
    state: AgentState,
    llm: BaseChatModel,
    timeout: float | None = None,
):
    query = state["original_query"]
    global_context = state["global_context"].model_dump()
    messages = state.get("messages", [])

    # turn_number는 supervisor가 항상 첫 번째로 실행되므로 여기서 증가시킨다.
    # engine.py에서 초기화하지 않으므로 체크포인터를 통해 턴 간 누적된다.
    current_turn = state.get("turn_number", 0) + 1

    # search_turn_history: 모든 검색 턴의 경량 메타데이터.
    search_turn_history = state.get("search_turn_history", [])
    slack_thread_context = state.get("slack_thread_context")

    static_prompt = prompt_loader.get_prompt(
        "rag/supervisor_static",
        sources=list(SOURCE_METADATA.values()),
        slack_thread_context=slack_thread_context,
    )
    dynamic_prompt = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=search_turn_history,
        slack_thread_context=slack_thread_context,
        **global_context,
    )
    system_message = build_system_message(
        static_prompt,
        dynamic_prompts=[dynamic_prompt],
    )

    # [SystemMessage] + 대화 이력(메시지 객체) + [HumanMessage(현재 질문)]
    history = get_conversation_history(messages)
    input_messages = [system_message, *history, HumanMessage(content=query)]

    token_usages = {"token_breakdown": {}}
    structured_llm = llm.with_structured_output(
        PipelinePlan,
        method="function_calling",
        include_raw=True,
    )

    await adispatch_custom_event(
        "process",
        {"status": "in_progress", "node": "supervisor"},
    )

    try:
        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=structured_llm,
            messages=input_messages,
            semaphore=service_semaphores.llm_large,
            timeout=timeout,
        )
        pipeline_plan: PipelinePlan = response.get("parsed")

        _NO_RETRIEVAL = {"direct_answer", "clarify"}

        event_content: dict = {"query_type": pipeline_plan.pipeline_type}
        if pipeline_plan.pipeline_type not in _NO_RETRIEVAL and pipeline_plan.query_topic:
            event_content["query_topic"] = pipeline_plan.query_topic

        await adispatch_custom_event(
            "process",
            {
                "status": "completed",
                "node": "supervisor",
                "reasoning": (
                    None
                    if pipeline_plan.pipeline_type in _NO_RETRIEVAL
                    else pipeline_plan.reasoning
                ),
                "content": event_content,
            },
        )
        intent = (
            "chitchat"
            if pipeline_plan.pipeline_type in _NO_RETRIEVAL
            else "search_pipeline"
        )

        logger.info(
            "supervisor_decision",
            pipeline_type=pipeline_plan.pipeline_type,
            max_iterations=pipeline_plan.max_iterations,
            inferred_tool_filters=[f.value for f in pipeline_plan.inferred_tool_filters]
            if pipeline_plan.inferred_tool_filters
            else None,
            search_history_len=len(search_turn_history),
            conversation_history_len=len(history),
        )

        # max_pipeline_type 상한 적용 (engine.py에서 mode → max_pipeline_type 변환)
        max_pipeline_type = state.get("max_pipeline_type", "complex")
        if _PIPELINE_ORDER.index(pipeline_plan.pipeline_type) > _PIPELINE_ORDER.index(
            max_pipeline_type
        ):
            logger.info(
                "pipeline_type_capped",
                original=pipeline_plan.pipeline_type,
                capped_to=max_pipeline_type,
            )
            pipeline_plan = pipeline_plan.model_copy(
                update={
                    "pipeline_type": max_pipeline_type,
                    "max_iterations": _DEFAULT_MAX_ITERATIONS[max_pipeline_type],
                }
            )

        result: dict = {
            "intent": intent,
            "pipeline_plan": pipeline_plan,
            "turn_number": current_turn,
            "query_topic": pipeline_plan.query_topic,
            **token_usages,
        }

        # rewrite 노드가 없는 파이프라인은 후속 노드가 rewritten_query를 참조하므로
        # supervisor에서 미리 original_query 값으로 채워둔다.
        _NO_REWRITE_PIPELINES = {"clarify", "direct_answer"}
        if pipeline_plan.pipeline_type in _NO_REWRITE_PIPELINES:
            result["rewritten_query"] = query

        # 사용자가 명시적 필터를 설정하지 않은 경우에만 LLM 추론 필터를 state에 적용
        user_tool_filters = state.get("tool_filters") or []
        if not user_tool_filters and pipeline_plan.inferred_tool_filters:
            result["tool_filters"] = pipeline_plan.inferred_tool_filters
            logger.info(
                "dynamic_tool_filters_applied",
                inferred_filters=[f.value for f in pipeline_plan.inferred_tool_filters],
            )

        return result

    except RETRYABLE_ERRORS as e:
        raise e
    except Exception as e:
        logger.warning(
            "supervisor_node_failed",
            error=str(e),
            exc_info=True,
            fallback="standard",
        )

        # 에러 이벤트 발송
        await adispatch_custom_event(
            "process",
            {
                "status": "error",
                "node": "supervisor",
                "reasoning": "질문 의도 파악에 실패했어요.",
            },
        )

        return {
            "intent": "search_pipeline",
            "pipeline_plan": None,
            "turn_number": state.get("turn_number", 0) + 1,
        }
