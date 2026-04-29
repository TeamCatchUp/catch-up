import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import build_docs_summary
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.schemas.structures import PipelinePlan
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()

_MAX_DOCS_SUMMARY = 20
_PIPELINE_ORDER = ["clarify", "direct_answer", "reuse", "simple", "standard", "complex"]
_DEFAULT_MAX_ITERATIONS: dict[str, int] = {
    "direct_answer": 0,
    "reuse": 0,
    "simple": 0,
    "standard": 3,
    "complex": 7,
}


@log_node
@token_usage
async def supervisor_node(state: AgentState, llm: BaseChatModel):
    query = state["original_query"]
    global_context = state["global_context"].model_dump()
    messages = state.get("messages", [])

    # turn_number는 supervisor가 항상 첫 번째로 실행되므로 여기서 증가시킨다.
    # engine.py에서 초기화하지 않으므로 체크포인터를 통해 턴 간 누적된다.
    current_turn = state.get("turn_number", 0) + 1

    # doc_cache는 세션 내 누적 검색 결과 전체. retrieved_docs(최근 1턴)보다 넓은 맥락을 제공한다.
    doc_cache = state.get("doc_cache", [])
    retrieved_docs_summary = build_docs_summary(doc_cache, max_docs=_MAX_DOCS_SUMMARY)

    system_prompt = prompt_loader.get_prompt(
        "rag/supervisor",
        retrieved_docs_summary=retrieved_docs_summary,
        **global_context,
    )
    system_message = build_system_message(system_prompt)

    # [SystemMessage] + 대화 이력(메시지 객체) + [HumanMessage(현재 질문)]
    history = get_conversation_history(messages)
    input_messages = [system_message, *history, HumanMessage(content=query)]

    token_usages = {"token_breakdown": {}}
    structured_llm = llm.with_structured_output(
        PipelinePlan,
        method="function_calling",
        include_raw=True,
    )

    try:
        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=structured_llm,
            messages=input_messages,
            semaphore=rag_semaphores.llm_large,
        )
        pipeline_plan: PipelinePlan = response.get("parsed")

        _NO_RETRIEVAL = {"direct_answer", "clarify"}
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
            doc_cache_size=len(doc_cache),
            history_len=len(history),
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
            **token_usages,
        }

        # rewrite 노드가 없는 파이프라인은 후속 노드가 rewritten_query를 참조하므로
        # supervisor에서 미리 original_query 값으로 채워둔다.
        _NO_REWRITE_PIPELINES = {"clarify", "direct_answer", "reuse", "simple"}
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

    except Exception as e:
        logger.warning(
            "supervisor_node_failed",
            error=str(e),
            exc_info=True,
            fallback="standard",
        )
        return {
            "intent": "search_pipeline",
            "pipeline_plan": None,
            "turn_number": state.get("turn_number", 0) + 1,
        }
