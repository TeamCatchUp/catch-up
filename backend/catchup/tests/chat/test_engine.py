import asyncio
import uuid
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from catchup.chat.engine import BACKGROUND_RUN_PROFILE
from catchup.chat.engine import SLACK_RUN_PROFILE
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
async def test_run_slack_profile_skips_reset_when_save_not_reached():
    """SLACK_RUN_PROFILE: 저장 이전 실패 시 reset을 호출하지 않는다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()
    sink = AsyncMock()

    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app") as mock_get_app:
            app = MagicMock()
            app.aget_state = AsyncMock(return_value=MagicMock(values={}))
            mock_get_app.return_value = app
            with patch.object(service, "_setup_config", return_value=({}, {}, None)):
                with patch.object(
                    service, "_resolve_input_messages", side_effect=RuntimeError("boom")
                ):
                    with patch.object(
                        service, "_save_message_content", AsyncMock()
                    ) as mock_save:
                        with patch.object(
                            service, "reset_last_turn", AsyncMock()
                        ) as mock_reset:
                            with patch.object(service, "_finalize_stats", AsyncMock()):
                                with patch("catchup.chat.engine.emit_audit_event"):
                                    await service.run(
                                        global_context,
                                        prompt_settings,
                                        session_id,
                                        sink,
                                        profile=SLACK_RUN_PROFILE,
                                        query="q",
                                    )

    mock_save.assert_not_called()
    mock_reset.assert_not_called()
    sink.assert_not_called()


@pytest.mark.asyncio
async def test_run_slack_profile_resets_on_error_without_partial_save():
    """SLACK_RUN_PROFILE: 저장 후 스트리밍 실패 시 partial 저장 없이 항상 reset한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()
    sink = AsyncMock()

    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=MagicMock(values={"messages": [HumanMessage(content="x")]})
    )
    app.astream_events = MagicMock(side_effect=RuntimeError("stream boom"))

    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app", return_value=app):
            with patch.object(service, "_setup_config", return_value=({}, {}, None)):
                with patch.object(
                    service, "_save_message_content", AsyncMock(return_value=999)
                ):
                    with patch.object(
                        service, "_save_partial_if_any", AsyncMock()
                    ) as mock_partial_save:
                        with patch.object(
                            service, "reset_last_turn", AsyncMock()
                        ) as mock_reset:
                            with patch.object(service, "_finalize_stats", AsyncMock()):
                                with patch("catchup.chat.engine.emit_audit_event"):
                                    await service.run(
                                        global_context,
                                        prompt_settings,
                                        session_id,
                                        sink,
                                        profile=SLACK_RUN_PROFILE,
                                        query="q",
                                    )

    mock_partial_save.assert_not_called()
    mock_reset.assert_called_once_with(room_id=42, session_id=session_id)


@pytest.mark.asyncio
async def test_run_slack_profile_reraises_cancelled_error():
    """SLACK_RUN_PROFILE: CancelledError는 반드시 재전파돼야 한다 (Slack 소비자에게 전달)."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()
    sink = AsyncMock()

    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=MagicMock(values={"messages": [HumanMessage(content="x")]})
    )
    app.astream_events = MagicMock(side_effect=asyncio.CancelledError())

    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app", return_value=app):
            with patch.object(service, "_setup_config", return_value=({}, {}, None)):
                with patch.object(
                    service, "_save_message_content", AsyncMock(return_value=999)
                ):
                    with patch.object(
                        service, "_save_partial_if_any", AsyncMock()
                    ) as mock_partial_save:
                        with patch.object(service, "_finalize_stats", AsyncMock()):
                            with patch("catchup.chat.engine.emit_audit_event"):
                                with pytest.raises(asyncio.CancelledError):
                                    await service.run(
                                        global_context,
                                        prompt_settings,
                                        session_id,
                                        sink,
                                        profile=SLACK_RUN_PROFILE,
                                        query="q",
                                    )

    mock_partial_save.assert_not_called()


@pytest.mark.asyncio
async def test_run_background_profile_saves_partial_on_error_without_reset():
    """BACKGROUND_RUN_PROFILE: partial content가 있으면 저장하고 reset은 하지 않는다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()
    sink = AsyncMock()

    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=MagicMock(values={"messages": [HumanMessage(content="x")]})
    )
    app.astream_events = MagicMock(side_effect=RuntimeError("stream boom"))

    fake_processor = MagicMock()
    fake_processor.context.accumulated_content = "이미 생성된 답변 일부"
    fake_processor.context.current_node = "generate_final_answer"

    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app", return_value=app):
            with patch.object(service, "_setup_config", return_value=({}, {}, None)):
                with patch.object(
                    service, "_save_message_content", AsyncMock(return_value=999)
                ):
                    with patch(
                        "catchup.chat.engine.ChatStreamProcessor",
                        return_value=fake_processor,
                    ):
                        with patch.object(
                            service, "_save_partial_if_any", AsyncMock()
                        ) as mock_partial_save:
                            with patch.object(
                                service, "reset_last_turn", AsyncMock()
                            ) as mock_reset:
                                with patch.object(service, "_finalize_stats", AsyncMock()):
                                    with patch("catchup.chat.engine.emit_audit_event"):
                                        await service.run(
                                            global_context,
                                            prompt_settings,
                                            session_id,
                                            sink,
                                            profile=BACKGROUND_RUN_PROFILE,
                                            query="q",
                                        )

    mock_partial_save.assert_called_once_with(fake_processor, 42, None)
    mock_reset.assert_not_called()


@pytest.mark.asyncio
async def test_run_background_profile_resets_when_no_partial_content_on_error():
    """BACKGROUND_RUN_PROFILE: partial content가 없으면 reset으로 폴백한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()
    sink = AsyncMock()

    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=MagicMock(values={"messages": [HumanMessage(content="x")]})
    )
    app.astream_events = MagicMock(side_effect=RuntimeError("stream boom"))

    fake_processor = MagicMock()
    fake_processor.context.accumulated_content = ""
    fake_processor.context.current_node = "supervisor"

    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app", return_value=app):
            with patch.object(service, "_setup_config", return_value=({}, {}, None)):
                with patch.object(
                    service, "_save_message_content", AsyncMock(return_value=999)
                ):
                    with patch(
                        "catchup.chat.engine.ChatStreamProcessor",
                        return_value=fake_processor,
                    ):
                        with patch.object(
                            service, "_save_partial_if_any", AsyncMock()
                        ) as mock_partial_save:
                            with patch.object(
                                service, "reset_last_turn", AsyncMock()
                            ) as mock_reset:
                                with patch.object(service, "_finalize_stats", AsyncMock()):
                                    with patch("catchup.chat.engine.emit_audit_event"):
                                        await service.run(
                                            global_context,
                                            prompt_settings,
                                            session_id,
                                            sink,
                                            profile=BACKGROUND_RUN_PROFILE,
                                            query="q",
                                        )

    mock_partial_save.assert_not_called()
    mock_reset.assert_called_once_with(room_id=42, session_id=session_id)


@pytest.mark.asyncio
async def test_run_background_profile_swallows_cancelled_error_and_saves_partial():
    """BACKGROUND_RUN_PROFILE: CancelledError는 재전파하지 않고 partial 저장만 시도한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()
    sink = AsyncMock()

    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=MagicMock(values={"messages": [HumanMessage(content="x")]})
    )
    app.astream_events = MagicMock(side_effect=asyncio.CancelledError())

    fake_processor = MagicMock()
    fake_processor.context.accumulated_content = "취소 직전까지의 답변"
    fake_processor.context.current_node = "generate_final_answer"

    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app", return_value=app):
            with patch.object(service, "_setup_config", return_value=({}, {}, None)):
                with patch.object(
                    service, "_save_message_content", AsyncMock(return_value=999)
                ):
                    with patch(
                        "catchup.chat.engine.ChatStreamProcessor",
                        return_value=fake_processor,
                    ):
                        with patch.object(
                            service, "_save_partial_if_any", AsyncMock()
                        ) as mock_partial_save:
                            with patch.object(service, "_finalize_stats", AsyncMock()):
                                with patch("catchup.chat.engine.emit_audit_event"):
                                    # CancelledError가 전파되지 않아야 한다
                                    await service.run(
                                        global_context,
                                        prompt_settings,
                                        session_id,
                                        sink,
                                        profile=BACKGROUND_RUN_PROFILE,
                                        query="q",
                                    )

    mock_partial_save.assert_called_once_with(fake_processor, 42, None)


@pytest.mark.asyncio
async def test_run_calls_on_complete_from_finally_even_if_graph_execution_raises():
    """run()의 finally는 그래프 실행이 실패해도 on_complete을 반드시 호출해야 한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    global_context.user.id = 1
    prompt_settings = MagicMock()
    sink = AsyncMock()
    on_complete = AsyncMock()

    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=MagicMock(values={"messages": [HumanMessage(content="x")]})
    )
    app.astream_events = MagicMock(side_effect=RuntimeError("stream boom"))

    with patch.object(service, "_ensure_chat_room", AsyncMock(return_value=42)):
        with patch.object(service, "_get_app", return_value=app):
            with patch.object(service, "_setup_config", return_value=({}, {}, None)):
                with patch.object(
                    service, "_save_message_content", AsyncMock(return_value=999)
                ):
                    with patch.object(service, "_save_partial_if_any", AsyncMock()):
                        with patch.object(service, "reset_last_turn", AsyncMock()):
                            with patch.object(service, "_finalize_stats", AsyncMock()):
                                with patch("catchup.chat.engine.emit_audit_event"):
                                    await service.run(
                                        global_context,
                                        prompt_settings,
                                        session_id,
                                        sink,
                                        profile=BACKGROUND_RUN_PROFILE,
                                        query="q",
                                        on_complete=on_complete,
                                    )

    on_complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_stats_processes_token_usage_and_flushes_langfuse():
    """base_config가 있으면 토큰 통계 처리와 langfuse rerank 갱신이 호출돼야 한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    base_config = {"configurable": {"thread_id": session_id}}

    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=MagicMock(values={"rerank_count": 2, "rerank_metadata": None})
    )
    service._app = app

    with patch.object(
        service, "_process_token_usage_stats"
    ) as mock_process_stats:
        with patch("catchup.chat.engine.settings") as mock_settings:
            mock_settings.ENABLE_LANGFUSE = False
            await service._finalize_stats(
                base_config, global_context, "trace-1", session_id
            )

    mock_process_stats.assert_called_once()


def test_run_profiles_preserve_recovery_matrix():
    """SLACK/BACKGROUND 프로파일이 설계에서 합의한 4개 조합을 정확히 인코딩해야 한다."""
    assert SLACK_RUN_PROFILE.save_partial is False
    assert SLACK_RUN_PROFILE.reraise_on_cancel is True
    assert BACKGROUND_RUN_PROFILE.save_partial is True
    assert BACKGROUND_RUN_PROFILE.reraise_on_cancel is False


@pytest.mark.asyncio
async def test_run_background_delegates_to_run_with_background_profile():
    """run_background는 event_store.publish를 sink로 하는 run()을 호출해야 한다."""
    service = ChatService()
    session_id = uuid.uuid4()
    global_context = MagicMock()
    prompt_settings = MagicMock()
    event_store = MagicMock()
    event_store.publish = AsyncMock()
    event_store.publish_done = AsyncMock()

    with patch.object(service, "run", AsyncMock()) as mock_run:
        await service.run_background(
            global_context=global_context,
            prompt_settings=prompt_settings,
            session_id=session_id,
            event_store=event_store,
            query="q",
        )

    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs["profile"] is BACKGROUND_RUN_PROFILE

    # run()의 4번째 위치 인자로 넘어간 sink가 event_store.publish로 위임되는지 확인
    sink_fn = mock_run.call_args.args[3]
    fake_event = MagicMock()
    await sink_fn(fake_event)
    event_store.publish.assert_awaited_once_with(str(session_id), fake_event)

    # run()에 넘겨진 on_complete가 event_store.publish_done으로 위임되는지 확인
    on_complete_fn = call_kwargs["on_complete"]
    await on_complete_fn()
    event_store.publish_done.assert_awaited_once_with(str(session_id))
