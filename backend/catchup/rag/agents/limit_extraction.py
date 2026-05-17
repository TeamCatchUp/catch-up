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

        # ToolMessage 내용을 plain text로 추출한다.
        # ToolMessage 객체를 직접 넘기면 Bedrock API가 대응하는 tool_use 블록이
        # 없다는 ValidationException을 발생시키므로 텍스트로 변환한다.
        search_results = "\n\n---\n\n".join(
            m.content
            for m in state.get("messages", [])
            if isinstance(m, ToolMessage) and m.content
        )
        user_message = HumanMessage(
            content=(
                f"Query: {query}\n\n"
                f"Search results:\n{search_results}"
            )
        )

        system_prompt = prompt_loader.get_prompt("rag/agent_limit_extraction")
        system_message = build_system_message(system_prompt)

        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=llm,
            messages=[system_message, user_message],
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
