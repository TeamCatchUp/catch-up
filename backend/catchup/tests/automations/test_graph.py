from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from catchup.automations.graph import build_inquiry_automation_graph
from catchup.automations.state import AutomationState
from catchup.db.models import SourceType
from catchup.rag.schemas.context import GlobalCompanyContext
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.context import GlobalCurrentTimeContext
from catchup.rag.schemas.context import GlobalUserContext
from catchup.rag.schemas.context import GlobalWorkspaceContext


def _make_global_context() -> GlobalContext:
    return GlobalContext(
        user=GlobalUserContext(id=1, name="테스터", email="test@example.com", department="CS"),
        workspace=GlobalWorkspaceContext(id=1, name="워크스페이스"),
        company=GlobalCompanyContext(id=1, name="컴퍼니"),
        current_time=GlobalCurrentTimeContext(),
    )


def _initial_state(inquiry: str = "환불 방법") -> AutomationState:
    return AutomationState(
        inquiry_text=inquiry,
        user_chat_id="chat-001",
        slack_channel_id="C123",
        slack_credential_id=1,
        global_context=_make_global_context(),
        messages=[HumanMessage(content=inquiry)],
        rewritten_query=inquiry,
        vector_search_queries=[],
        retrieved_docs=[],
        tool_filters=[SourceType.CHANNEL_TALK],
        rerank_count=0,
        grade_result=None,
        guide_text=None,
    )


def _make_slack_mocks(user_chat_id: str = "chat-001"):
    mock_token = MagicMock()
    mock_token.bot_access_token = "xoxb-test"
    mock_token.team_id = "T123"
    mock_client = AsyncMock()
    mock_client.get_conversation_history.return_value = {
        "messages": [
            {
                "ts": "1700000000.000000",
                "bot_id": "B123",
                "text": f"https://example.com/user-chats/{user_chat_id}",
            }
        ],
        "has_more": False,
    }
    return mock_token, mock_client


@pytest.mark.asyncio
async def test_graph_reusable_path():
    """grade=True 경로: rerank 없이 generate_guide → send_slack으로 진행한다."""
    docs = [Document(page_content="환불은 마이페이지에서 가능합니다.", id="d1")]

    mock_llm_small = MagicMock()
    mock_llm_small.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=MagicMock(vector_search_queries=[])
    )

    mock_llm_grade = MagicMock()
    mock_llm_grade.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=MagicMock(reusable=True, reason="해결 방법 포함")
    )

    mock_llm_large = MagicMock()
    mock_llm_large.ainvoke = AsyncMock(
        return_value=MagicMock(content="마이페이지에서 환불 신청을 안내하세요.")
    )

    mock_vector_db = MagicMock()
    mock_vector_db.hybrid_search_batch = AsyncMock(return_value=[docs])

    mock_rerank = MagicMock()
    mock_token, mock_slack_client = _make_slack_mocks()

    with (
        patch(
            "catchup.automations.nodes.send_slack.get_slack_token_by_id",
            return_value=mock_token,
        ),
        patch(
            "catchup.automations.nodes.send_slack.SlackApiClientWrapper",
            return_value=mock_slack_client,
        ),
        patch("catchup.automations.nodes.send_slack.SessionLocal"),
        patch(
            "catchup.automations.nodes.grade.prompt_loader.get_prompt",
            return_value=[MagicMock()],
        ),
        patch(
            "catchup.automations.nodes.generate_guide.prompt_loader.get_prompt",
            return_value=[MagicMock()],
        ),
        patch(
            "catchup.rag.nodes.generate_vector_queries.generate_vector_queries"
            ".prompt_loader.get_prompt",
            return_value=[MagicMock()],
        ),
    ):
        graph = build_inquiry_automation_graph(
            llm_small=mock_llm_small,
            llm_grade=mock_llm_grade,
            llm_large=mock_llm_large,
            vector_db_service=mock_vector_db,
            rerank_service=mock_rerank,
        )
        final_state = await graph.ainvoke(_initial_state())

    assert final_state["grade_result"].reusable is True
    assert final_state["guide_text"] is not None


@pytest.mark.asyncio
async def test_graph_not_reusable_path():
    """grade=False 경로: hybrid search → rerank → generate_guide → send_slack으로 진행한다."""
    docs = [Document(page_content="일반적인 내용.", id="d1")]

    mock_llm_small = MagicMock()
    mock_llm_small.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=MagicMock(vector_search_queries=[])
    )

    mock_llm_grade = MagicMock()
    mock_llm_grade.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=MagicMock(reusable=False, reason="구체적 해결책 없음")
    )

    mock_llm_large = MagicMock()
    mock_llm_large.ainvoke = AsyncMock(
        return_value=MagicMock(content="에스컬레이션이 필요합니다.")
    )

    mock_vector_db = MagicMock()
    mock_vector_db.hybrid_search_batch = AsyncMock(return_value=[docs])

    mock_rerank_service = MagicMock()
    mock_token, mock_slack_client = _make_slack_mocks()

    with (
        patch(
            "catchup.automations.nodes.send_slack.get_slack_token_by_id",
            return_value=mock_token,
        ),
        patch(
            "catchup.automations.nodes.send_slack.SlackApiClientWrapper",
            return_value=mock_slack_client,
        ),
        patch("catchup.automations.nodes.send_slack.SessionLocal"),
        patch(
            "catchup.automations.nodes.grade.prompt_loader.get_prompt",
            return_value=[MagicMock()],
        ),
        patch(
            "catchup.automations.nodes.generate_guide.prompt_loader.get_prompt",
            return_value=[MagicMock()],
        ),
        patch(
            "catchup.rag.nodes.generate_vector_queries.generate_vector_queries"
            ".prompt_loader.get_prompt",
            return_value=[MagicMock()],
        ),
        patch("catchup.rag.nodes.rerank.rerank.rag_semaphores"),
    ):
        graph = build_inquiry_automation_graph(
            llm_small=mock_llm_small,
            llm_grade=mock_llm_grade,
            llm_large=mock_llm_large,
            vector_db_service=mock_vector_db,
            rerank_service=mock_rerank_service,
        )
        final_state = await graph.ainvoke(_initial_state())

    assert final_state["grade_result"].reusable is False
    assert final_state["guide_text"] is not None
