import uuid
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from catchup.chat.engine import ChatService


def test_resolve_input_messages_first_turn_no_duplication():
    """첫 턴: DB가 비어있고 graph state도 비었을 때 query가 한 번만 들어가야 한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    query = "test query"

    lg_current_state = MagicMock()
    lg_current_state.values = {}

    with patch("catchup.chat.engine.restore_conversation_context") as mock_restore:
        mock_restore.return_value = []

        with patch("catchup.chat.engine.SessionLocal"):
            messages = service._resolve_input_messages(
                session_id=session_id,
                query=query,
                lg_current_state=lg_current_state,
                additional_context=None,
            )

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == query


def test_resolve_input_messages_state_empty_with_db_history():
    """state_empty 분기: DB의 과거 턴들 + 현재 query, 중복 없이 결합되어야 한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    query = "current question"

    lg_current_state = MagicMock()
    lg_current_state.values = {}

    past = [
        HumanMessage(content="prev question"),
        AIMessage(content="prev answer"),
    ]

    with patch("catchup.chat.engine.restore_conversation_context") as mock_restore:
        mock_restore.return_value = past

        with patch("catchup.chat.engine.SessionLocal"):
            messages = service._resolve_input_messages(
                session_id=session_id,
                query=query,
                lg_current_state=lg_current_state,
                additional_context=None,
            )

    assert len(messages) == 3
    assert messages[0].content == "prev question"
    assert messages[1].content == "prev answer"
    assert isinstance(messages[2], HumanMessage)
    assert messages[2].content == query


def test_resolve_input_messages_uses_graph_state_when_present():
    """has_history_in_graph 분기: DB 복원 없이 현재 turn 메시지만 반환."""
    service = ChatService()
    session_id = uuid.uuid4()
    query = "next question"

    lg_current_state = MagicMock()
    lg_current_state.values = {"messages": [HumanMessage(content="anything")]}

    with patch("catchup.chat.engine.restore_conversation_context") as mock_restore:
        messages = service._resolve_input_messages(
            session_id=session_id,
            query=query,
            lg_current_state=lg_current_state,
            additional_context=None,
        )

    mock_restore.assert_not_called()
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == query


@pytest.mark.asyncio
async def test_chat_stream_skips_reset_when_save_not_reached():
    """저장 이전 단계에서 실패하면 reset_last_turn을 호출하지 않아야 한다 (이전 턴 보호)."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()

    # _ensure_chat_room 통과, _resolve_input_messages에서 실패하도록 구성
    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app") as mock_get_app:
            app = MagicMock()
            app.aget_state = AsyncMock(return_value=MagicMock(values={}))
            mock_get_app.return_value = app
            with patch.object(
                service, "_setup_config", return_value=({}, {}, None)
            ):
                with patch.object(
                    service,
                    "_resolve_input_messages",
                    side_effect=RuntimeError("boom"),
                ):
                    with patch.object(
                        service, "_save_message_content", AsyncMock()
                    ) as mock_save:
                        with patch.object(
                            service, "reset_last_turn", AsyncMock()
                        ) as mock_reset:
                            with patch("catchup.chat.engine.emit_audit_event"):
                                async for _ in service.chat_stream(
                                    global_context=global_context,
                                    prompt_settings=prompt_settings,
                                    session_id=session_id,
                                    query="q",
                                ):
                                    pass

    mock_save.assert_not_called()
    mock_reset.assert_not_called()


@pytest.mark.asyncio
async def test_chat_stream_calls_reset_when_save_succeeded():
    """저장 후 단계에서 실패하면 reset_last_turn으로 정리해야 한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()

    # _save_message_content는 성공, 그 다음 단계(스트리밍)에서 실패
    app = MagicMock()
    app.aget_state = AsyncMock(return_value=MagicMock(values={"messages": [HumanMessage(content="x")]}))
    app.astream_events = MagicMock(side_effect=RuntimeError("stream boom"))

    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app", return_value=app):
            with patch.object(
                service, "_setup_config", return_value=({}, {}, None)
            ):
                with patch.object(
                    service, "_save_message_content", AsyncMock(return_value=999)
                ):
                    with patch(
                        "catchup.chat.engine.run_in_threadpool",
                        AsyncMock(return_value=42),
                    ):
                        with patch.object(
                            service, "reset_last_turn", AsyncMock()
                        ) as mock_reset:
                            with patch("catchup.chat.engine.emit_audit_event"):
                                async for _ in service.chat_stream(
                                    global_context=global_context,
                                    prompt_settings=prompt_settings,
                                    session_id=session_id,
                                    query="q",
                                ):
                                    pass

    mock_reset.assert_called_once()
