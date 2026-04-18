import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from catchup.costs.utils import extract_token_usages
from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import log_node
from catchup.rag.nodes.utils import resolve_temporal_context
from catchup.rag.schemas.structures import PipelinePlan
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()

_MAX_DOCS_SUMMARY = 20
_PIPELINE_ORDER = ["chitchat", "reuse", "simple", "standard", "complex"]
_DEFAULT_MAX_ITERATIONS: dict[str, int] = {
    "chitchat": 0, "reuse": 0, "simple": 0, "standard": 3, "complex": 7
}


@log_node
@token_usage
async def supervisor_node(state: AgentState, llm: BaseChatModel):
    query = state["original_query"]
    global_context = state["global_context"].model_dump()
    messages = state.get("messages", [])
    retrieved_docs = state.get("retrieved_docs", [])

    # reuse 판단은 "얼마나 오래됐는가"가 아니라 "현재 질문과 맥락이 이어지는가"의 문제.
    # 턴 카운트나 타임스탬프 기반 필터링 없이 항상 supervisor LLM에게 문서 요약을 제공하고,
    # LLM이 대화 이력과 함께 보고 의미적으로 직접 판단한다.
    retrieved_docs_summary = _build_docs_summary(retrieved_docs)

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
        async with rag_semaphores.final_answer:
            raw_response = await structured_llm.ainvoke(input=input_messages)
            token_usages = extract_token_usages(raw_response.get("raw"))
            pipeline_plan: PipelinePlan = raw_response.get("parsed")

        intent = "chitchat" if pipeline_plan.pipeline_type == "chitchat" else "search_pipeline"

        logger.info(
            "supervisor_decision",
            pipeline_type=pipeline_plan.pipeline_type,
            max_iterations=pipeline_plan.max_iterations,
            retrieved_docs_count=len(retrieved_docs),
            history_len=len(history),
        )

        # max_pipeline_type 상한 적용 (engine.py에서 mode → max_pipeline_type 변환)
        max_pipeline_type = state.get("max_pipeline_type", "complex")
        if _PIPELINE_ORDER.index(pipeline_plan.pipeline_type) > _PIPELINE_ORDER.index(max_pipeline_type):
            logger.info(
                "pipeline_type_capped",
                original=pipeline_plan.pipeline_type,
                capped_to=max_pipeline_type,
            )
            pipeline_plan = pipeline_plan.model_copy(update={
                "pipeline_type": max_pipeline_type,
                "max_iterations": _DEFAULT_MAX_ITERATIONS[max_pipeline_type],
            })

        result: dict = {
            "intent": intent,
            "pipeline_plan": pipeline_plan,
            **token_usages,
        }

        # rewrite 노드가 없는 파이프라인은 후속 노드가 rewritten_query를 참조하므로
        # supervisor에서 미리 original_query 값으로 채워둔다.
        _NO_REWRITE_PIPELINES = {"chitchat", "reuse", "simple"}
        if pipeline_plan.pipeline_type in _NO_REWRITE_PIPELINES:
            result["rewritten_query"] = query

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
        }


def _build_docs_summary(docs: list[Document]) -> str:
    """Supervisor의 reuse 판단을 위한 retrieved_docs 요약 생성.

    reuse 여부는 문서의 시간적 신선도가 아니라 현재 대화 맥락과의 의미적 관련성으로
    판단해야 하므로, 기계적 stale 필터링 없이 항상 전체 요약을 반환한다.
    """
    if not docs:
        return ""

    shown = docs[:_MAX_DOCS_SUMMARY]
    lines = []
    for i, doc in enumerate(shown, 1):
        source = doc.metadata.get("source", "unknown")
        # page_content: ingestion 시점에 생성된 영문 요약 (Confluence 제외)
        # Confluence는 요약 없이 원문이 들어있으므로 contextual_content를 슬라이싱
        if source == "confluence":
            content = (doc.metadata.get("contextual_content") or "")[:200]
        else:
            content = doc.page_content
        temporal = resolve_temporal_context(doc.metadata)
        lines.append(f"[{i}] (Source: {source}) {temporal}\n{content}")
    if len(docs) > _MAX_DOCS_SUMMARY:
        lines.append(f"... and {len(docs) - _MAX_DOCS_SUMMARY} more documents.")
    return "\n\n".join(lines)
