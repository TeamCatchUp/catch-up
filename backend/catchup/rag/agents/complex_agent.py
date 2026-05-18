import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.callbacks import adispatch_custom_event
from langchain_core.messages import HumanMessage

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.agents.tools.search_tools import REACT_TOOLS
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import build_docs_summary
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import coerce_message_text
from catchup.rag.nodes.utils import drop_orphaned_tool_calls
from catchup.rag.nodes.utils import extract_essential_ids_from_agent_view
from catchup.rag.nodes.utils import extract_reason_for_stopping
from catchup.rag.nodes.utils import log_node
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.schemas.sources import SOURCE_METADATA
from catchup.rag.schemas.structures import SearchPlan
from catchup.rag.schemas.structures import SearchStep
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState
from catchup.rag.static_reasoning import get_static_reasoning

logger = structlog.get_logger()


@log_node
@token_usage
async def complex_planner_node(
    state: AgentState,
    llm: BaseChatModel,
    timeout: float | None = None,
):
    """Complex 파이프라인 플래너. Extended Thinking LARGE 모델로 검색 전략을 수립한다."""
    global_context = state["global_context"].model_dump()
    query = state.get("rewritten_query") or state.get("original_query", "")

    system_prompt = prompt_loader.get_prompt(
        "rag/complex_planner_system",
        **global_context,
    )
    system_message = build_system_message(system_prompt)

    structured_llm = llm.with_structured_output(
        SearchPlan,
        method="function_calling",
        include_raw=True,
    )

    await adispatch_custom_event(
        "process",
        {
            "status": "in_progress",
            "node": "complex_planner",
            "reasoning": get_static_reasoning("complex_planner"),
        },
    )

    try:
        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=structured_llm,
            messages=[system_message, HumanMessage(content=query)],
            semaphore=rag_semaphores.llm_small,
            timeout=timeout,
        )
        plan: SearchPlan = response.get("parsed")
    except RETRYABLE_ERRORS as e:
        raise e
    except Exception as e:
        logger.warning("complex_planner_failed", error=str(e), exc_info=True)
        await adispatch_custom_event(
            "process",
            {
                "status": "error",
                "node": "complex_planner",
                "reasoning": "검색 계획 수립에 실패했어요.",
            },
        )
        return {"search_plan": []}  # None=미시도, []=실패, [steps]=성공

    step_count = len(plan.steps) if plan else 0
    logger.info("complex_plan_created", step_count=step_count)
    if plan:
        logger.debug(
            "complex_plan_steps",
            steps=[
                {
                    "step": s.step,
                    "intent": s.intent,
                    "queries": s.queries,
                    "parallel": s.parallel,
                }
                for s in plan.steps
            ],
        )
        for s in plan.steps:
            await adispatch_custom_event(
                "process",
                {
                    "status": "completed",
                    "node": "complex_planner",
                    "content": {"step": s.step, "intent": s.intent},
                },
            )

    return {
        "search_plan": plan.steps if plan else None,
        **token_usages,
    }


@log_node
@token_usage
async def complex_agent_node(
    state: AgentState,
    llm: BaseChatModel,
):
    """Complex ReAct 에이전트 노드이다. LARGE 모델, max_iter=7을 사용한다.
    search_plan과 accumulated_docs를 참조해 다음 검색 전략을 결정한다."""
    pipeline_plan = state.get("pipeline_plan")
    max_iterations = pipeline_plan.max_iterations if pipeline_plan else 7
    agent_iteration = state.get("agent_iteration", 0)

    if agent_iteration >= max_iterations:
        logger.info("complex_agent_max_iterations_reached", iterations=agent_iteration)
        return {
            "agent_iteration": agent_iteration,
            "agent_stop_reason": "iteration_limit",
        }

    search_plan = state.get("search_plan") or []
    accumulated_docs = state.get("accumulated_docs", [])
    cached_docs = state.get("retrieved_docs", []) if agent_iteration == 0 else []
    global_context = state["global_context"].model_dump()

    system_prompt = prompt_loader.get_prompt(
        "rag/complex_agent_system",
        search_plan_text=_format_search_plan(search_plan),
        accumulated_docs_summary=build_docs_summary(accumulated_docs),
        cached_docs_summary=build_docs_summary(cached_docs) if cached_docs else "",
        sources=list(SOURCE_METADATA.values()),
        **global_context,
    )
    system_message = build_system_message(system_prompt)
    query = state.get("rewritten_query") or state.get("original_query", "")

    llm_with_tools = llm.bind_tools(REACT_TOOLS, stop=["<stop/>"])

    await adispatch_custom_event(
        "process",
        {"status": "in_progress", "node": "complex_agent"},
    )

    existing_messages = drop_orphaned_tool_calls(state.get("messages", []))
    try:
        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=llm_with_tools,
            messages=[system_message, HumanMessage(content=query)] + existing_messages,
            semaphore=rag_semaphores.llm_small,
        )
    except RETRYABLE_ERRORS as e:
        raise e
    except Exception:
        return {"agent_iteration": agent_iteration + 1}

    tool_calls = getattr(response, "tool_calls", None) or []
    logger.info(
        "complex_agent_decision",
        iteration=agent_iteration + 1,
        accumulated_docs_count=len(accumulated_docs),
        has_tool_calls=bool(tool_calls),
        tool_names=[tc["name"] for tc in tool_calls],
    )
    if tool_calls:
        logger.debug(
            "complex_agent_tool_calls",
            calls=[{"name": tc["name"], "args": tc["args"]} for tc in tool_calls],
        )

    # 에이전트가 더 이상 도구를 호출하지 않으면(루프 종료), 자신의 판단을 state에 기록해 답변 노드에 전달한다.
    reasoning_update = {}
    reasoning = coerce_message_text(response.content)
    if not tool_calls:
        essential_ids = extract_essential_ids_from_agent_view(
            reasoning,
            accumulated_docs,
            state.get("agent_seen_doc_ids") or [],
        )
        reasoning_update = {
            "agent_reasoning": reasoning,
            "essential_doc_ids": list(essential_ids) if essential_ids else [],
            "agent_stop_reason": "by_choice",
        }

    if reasoning:
        display_reasoning = (
            extract_reason_for_stopping(reasoning) if not tool_calls else reasoning
        )
        await adispatch_custom_event(
            "process",
            {"status": "completed", "node": "complex_agent", "reasoning": display_reasoning},
        )

    return {
        "messages": [response],
        "agent_iteration": agent_iteration + 1,
        **reasoning_update,
        **token_usages,
    }


def _format_search_plan(steps: list[SearchStep]) -> str:
    if not steps:
        return ""
    lines = []
    for step in steps:
        deps = f" [선행 step 필요: {step.depends_on}]" if step.depends_on else ""
        parallel_note = " [병렬 실행]" if step.parallel else ""
        lines.append(f"Step {step.step}{parallel_note}{deps}: {step.intent}")
        for q in step.queries:
            lines.append(f"  - {q}")
    return "\n".join(lines)
