import asyncio

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
from catchup.rag.nodes.utils import extract_essential_ids
from catchup.rag.nodes.utils import extract_reason_for_stopping
from catchup.rag.nodes.utils import log_node
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def standard_agent_node(
    state: AgentState,
    llm: BaseChatModel,
    timeout: float | None = None,
):
    """Standard ReAct 에이전트. SMALL 모델, max_iter=3.
    accumulated_docs를 보고 추가 검색 여부를 판단해 tool을 호출한다."""
    pipeline_plan = state.get("pipeline_plan")
    max_iterations = pipeline_plan.max_iterations if pipeline_plan else 3
    agent_iteration = state.get("agent_iteration", 0)

    if agent_iteration >= max_iterations:
        logger.info("standard_agent_max_iterations_reached", iterations=agent_iteration)
        return {"agent_iteration": agent_iteration}

    accumulated_docs = state.get("accumulated_docs", [])
    global_context = state["global_context"].model_dump()

    system_prompt = prompt_loader.get_prompt(
        "rag/standard_agent_system",
        accumulated_docs_summary=build_docs_summary(accumulated_docs),
        **global_context,
    )
    system_message = build_system_message(system_prompt)
    query = state.get("rewritten_query") or state.get("original_query", "")

    llm_with_tools = llm.bind_tools(REACT_TOOLS)

    await adispatch_custom_event(
        "process",
        {"status": "in_progress", "node": "standard_agent"},
    )

    existing_messages = drop_orphaned_tool_calls(state.get("messages", []))
    try:
        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=llm_with_tools,
            messages=[system_message, HumanMessage(content=query)] + existing_messages,
            semaphore=rag_semaphores.llm_large,
            timeout=timeout,
        )
    except asyncio.TimeoutError as e:
        raise e
    except Exception:
        return {"agent_iteration": agent_iteration + 1}

    tool_calls = getattr(response, "tool_calls", None) or []
    logger.info(
        "standard_agent_decision",
        iteration=agent_iteration + 1,
        accumulated_docs_count=len(accumulated_docs),
        has_tool_calls=bool(tool_calls),
        tool_names=[tc["name"] for tc in tool_calls],
    )
    if tool_calls:
        logger.debug(
            "standard_agent_tool_calls",
            calls=[{"name": tc["name"], "args": tc["args"]} for tc in tool_calls],
        )

    # 에이전트가 더 이상 도구를 호출하지 않으면(루프 종료), 자신의 판단을 state에 기록해 답변 노드에 전달한다.
    reasoning_update = {}
    reasoning = coerce_message_text(response.content)
    if not tool_calls:
        essential_ids = extract_essential_ids(reasoning, accumulated_docs)
        reasoning_update = {
            "agent_reasoning": reasoning,
            "essential_doc_ids": list(essential_ids) if essential_ids else [],
        }

    if reasoning:
        display_reasoning = (
            extract_reason_for_stopping(reasoning) if not tool_calls else reasoning
        )
        await adispatch_custom_event(
            "process",
            {"status": "completed", "node": "standard_agent", "reasoning": display_reasoning},
        )

    return {
        "messages": [response],
        "agent_iteration": agent_iteration + 1,
        **reasoning_update,
        **token_usages,
    }


_RERANK_INPUT_WINDOW = 300  # reranker 입력 상한이다.


async def collect_docs_node(state: AgentState):
    """accumulated_docs를 retrieved_docs로 복사해 rerank → generate 노드가 참조할 수 있게 한다.
    reranker 입력 크기를 _RERANK_INPUT_WINDOW 이내로 제한하며, 점수(score) 기반으로 상위 문서를 우선 선발한다."""
    accumulated = state.get("accumulated_docs", [])

    # 점수 내림차순 정렬 (점수가 없는 경우 0.0으로 처리)
    sorted_docs = sorted(
        accumulated, key=lambda d: d.metadata.get("score", 0.0), reverse=True
    )

    capped = sorted_docs[:_RERANK_INPUT_WINDOW]
    logger.info(
        "collect_docs",
        total_accumulated=len(accumulated),
        passed_to_reranker=len(capped),
        capped=len(accumulated) > _RERANK_INPUT_WINDOW,
    )

    return {"retrieved_docs": capped}
