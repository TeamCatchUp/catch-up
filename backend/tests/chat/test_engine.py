import uuid
from unittest.mock import MagicMock
from unittest.mock import patch

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
