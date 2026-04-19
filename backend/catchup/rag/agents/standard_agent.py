from collections import Counter

import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from catchup.costs.utils import extract_token_usages
from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.agents.tools.search_tools import REACT_TOOLS
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import log_node
from catchup.rag.nodes.utils import resolve_temporal_context
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def standard_agent_node(state: AgentState, llm: BaseChatModel):
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
        accumulated_docs_summary=_build_docs_summary(accumulated_docs),
        **global_context,
    )
    system_message = build_system_message(system_prompt)
    query = state.get("rewritten_query") or state.get("original_query", "")

    llm_with_tools = llm.bind_tools(REACT_TOOLS)
    token_usages = {"token_breakdown": {}}

    try:
        async with rag_semaphores.analysis:
            response: AIMessage = await llm_with_tools.ainvoke(
                input=[system_message, HumanMessage(content=query)]
            )
            token_usages = extract_token_usages(response)
    except Exception as e:
        logger.warning("standard_agent_node_failed", error=str(e), exc_info=True)
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

    return {
        "messages": [response],
        "agent_iteration": agent_iteration + 1,
        **token_usages,
    }


_RERANK_INPUT_WINDOW = 300  # reranker 입력 상한


async def collect_docs_node(state: AgentState):
    """accumulated_docs를 retrieved_docs로 복사해 rerank → generate 노드가 참조할 수 있게 한다.
    reranker 입력 크기를 _RERANK_INPUT_WINDOW 이내로 제한한다."""
    accumulated = state.get("accumulated_docs", [])
    capped = accumulated[:_RERANK_INPUT_WINDOW]
    logger.info(
        "collect_docs",
        total_accumulated=len(accumulated),
        passed_to_reranker=len(capped),
        capped=len(accumulated) > _RERANK_INPUT_WINDOW,
    )
    return {"retrieved_docs": capped}


def _build_docs_summary(docs: list[Document]) -> str:
    if not docs:
        return "아직 수집된 문서 없음"

    source_counts = Counter(d.metadata.get("source", "unknown") for d in docs)
    source_str = ", ".join(f"{src}:{cnt}" for src, cnt in source_counts.items())
    lines = [f"총 {len(docs)}개 문서 수집됨 ({source_str})", ""]

    for i, doc in enumerate(docs[:5], 1):
        source = doc.metadata.get("source", "unknown")
        temporal = resolve_temporal_context(doc.metadata)
        snippet = doc.page_content[:100].replace("\n", " ")
        lines.append(f"[{i}] ({source}) {temporal}\n{snippet}")

    if len(docs) > 5:
        lines.append(f"... 외 {len(docs) - 5}개")

    return "\n".join(lines)
