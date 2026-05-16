# backend/catchup/rag/agents/limit_extraction.py
import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.messages import ToolMessage

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import build_system_message
from catchup.rag.nodes.utils import coerce_message_text
from catchup.rag.nodes.utils import drop_orphaned_tool_calls
from catchup.rag.nodes.utils import extract_essential_ids_from_agent_view
from catchup.rag.nodes.utils import log_node
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def extract_essential_node(
    state: AgentState,
    llm: BaseChatModel,
) -> dict:
    """Iteration limit 도달 후 경량 LLM으로 essential doc IDs를 추출한다.

    state['messages']는 읽기 전용으로 사용하며 수정하지 않는다.
    프론트 progress 이벤트는 발생시키지 않는다.
    예외 발생 시 빈 dict을 반환해 essential_doc_ids를 변경하지 않는다.
    """
    try:
        query = state.get("rewritten_query") or state.get("original_query", "")
        all_messages = drop_orphaned_tool_calls(state.get("messages", []))
        existing_messages = [
            m for m in all_messages if isinstance(m, ToolMessage)
        ]

        system_prompt = prompt_loader.get_prompt("rag/agent_limit_extraction")
        system_message = build_system_message(system_prompt)

        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=llm,
            messages=[system_message, HumanMessage(content=query)]
            + existing_messages,
            semaphore=rag_semaphores.llm_small,
            timeout=10.0,
        )

        reasoning = coerce_message_text(response.content)
        essential_ids = extract_essential_ids_from_agent_view(
            reasoning,
            state.get("accumulated_docs", []),
            state.get("agent_seen_doc_ids") or [],
        )
        logger.info(
            "extract_essential_completed",
            essential_count=len(essential_ids),
        )
        return {
            "essential_doc_ids": list(essential_ids),
            **token_usages,
        }
    except Exception:
        logger.warning("extract_essential_failed", exc_info=True)
        return {}
