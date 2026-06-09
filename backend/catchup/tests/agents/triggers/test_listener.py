from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from catchup.agents.triggers import listener
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.agents.triggers.stream import AgentRunRequest
from catchup.agents.triggers.stream import AgentRunStreamMessage
from catchup.agents.triggers.stream import decode_agent_run_stream_entries
from catchup.db.models import AgentTrigger
from catchup.db.models import AgentTriggerRun
from catchup.db.models import AgentTriggerRunStatus


@pytest.mark.asyncio
async def test_process_agent_run_message_commits_execution_claim_before_run(monkeypatch) -> None:
    order: list[str] = []
    db = Mock()
    context = listener.AgentRunExecutionContext(
        run_id=123,
        message_id="stream-1",
        spec_id=456,
        spec=Mock(),
        raw_spec={},
        user_input_values={},
        event=AgentWebhookEvent(
            event_id="event-1",
            external_event_id="event-1",
            source="channel_talk",
            event_type="user_chat.new_message",
            payload={"channel_id": "ch-001"},
        ),
        global_context=Mock(),
    )
    message = AgentRunStreamMessage(
        message_id="stream-1",
        request=AgentRunRequest(
            run_id=123,
            trigger_id=1,
            agent_spec_id=456,
            event_id="event-1",
            policy_kind="immediate",
        ),
    )

    db.commit.side_effect = lambda: order.append("claim_commit")
    monkeypatch.setattr(listener, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        listener,
        "run_agent_request",
        lambda **_: listener.AgentRunProcessResult(
            should_ack=False,
            execution=context,
        ),
    )

    async def execute_agent_run(_context):
        order.append("execute")
        return "ok", None

    async def ack_message(_message_id):
        order.append("ack")

    monkeypatch.setattr(
        listener,
        "_mark_execution_started",
        lambda _context: order.append("start_commit") or True,
    )
    monkeypatch.setattr(listener, "_execute_agent_run", execute_agent_run)
    monkeypatch.setattr(
        listener,
        "_record_agent_run_terminal_state",
        lambda **_: order.append("terminal_commit") or True,
    )
    monkeypatch.setattr(listener, "ack_agent_run_message", ack_message)

    await listener.process_agent_run_message(message)

    assert order == ["claim_commit", "start_commit", "execute", "terminal_commit", "ack"]


def test_run_agent_request_rejects_stream_fields_that_do_not_match_db_state() -> None:
    run = SimpleNamespace(
        id=123,
        trigger_id=1,
        latest_event_id="event-1",
        policy_kind="immediate",
        status=AgentTriggerRunStatus.DISPATCHING,
        dispatch_token="token-1",
    )
    trigger = SimpleNamespace(id=1, agent_spec_id=456)
    db = Mock()
    db.get.side_effect = lambda model, _id: {
        AgentTriggerRun: run,
        AgentTrigger: trigger,
    }[model]

    result = listener.run_agent_request(
        db=db,
        message_id="stream-1",
        request=AgentRunRequest(
            run_id=123,
            trigger_id=1,
            agent_spec_id=999,
            event_id="event-1",
            policy_kind="immediate",
            dispatch_token="token-1",
        ),
    )

    assert result.should_ack is True
    assert result.execution is None
    db.execute.assert_not_called()


def test_decode_agent_run_stream_entries_decodes_bytes_keys_from_redis() -> None:
    messages = decode_agent_run_stream_entries(
        [
            (
                b"1-0",
                {
                    b"run_id": b"123",
                    b"trigger_id": b"1",
                    b"agent_spec_id": b"456",
                    b"event_id": b"event-1",
                    b"policy_kind": b"immediate",
                    b"dispatch_token": b"token-1",
                },
            )
        ]
    )

    assert len(messages) == 1
    assert messages[0].malformed is False
    assert messages[0].message_id == "1-0"
    assert messages[0].request == AgentRunRequest(
        run_id=123,
        trigger_id=1,
        agent_spec_id=456,
        event_id="event-1",
        policy_kind="immediate",
        dispatch_token="token-1",
    )


@pytest.mark.asyncio
async def test_execute_agent_run_skips_execution_for_channeltalk_with_invalid_config(
    monkeypatch,
) -> None:
    """채널톡 이벤트이지만 InquiryAutomationConfig 파싱 실패 시 조용히 성공 반환한다."""
    context = listener.AgentRunExecutionContext(
        run_id=123,
        message_id="stream-1",
        spec_id=456,
        spec=None,
        raw_spec={},
        user_input_values={},
        event=AgentWebhookEvent(
            event_id="event-1",
            source="channel_talk",
            event_type="user_chat.new_message",
            payload={
                "entity": {
                    "channelId": "ch-001",
                    "chatType": "userChat",
                    "chatId": "chat-1",
                },
            },
        ),
        global_context=Mock(),
    )
    monkeypatch.setattr(
        listener,
        "build_channel_talk_user_chat_inputs",
        AsyncMock(return_value={"channel_talk_user_chat_context": "assembled"}),
    )

    result, error = await listener._execute_agent_run(context)

    assert result == ""
    assert error is None


@pytest.mark.asyncio
async def test_build_automation_input_reads_inquiry_automation_config(
    monkeypatch,
) -> None:
    from catchup.automations.config import INQUIRY_AUTOMATION_PRESET_KEY
    from catchup.automations.config import InquiryAutomationConfig

    config = InquiryAutomationConfig(
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_credential_id=1,
        slack_channel_id="C123",
        slack_credential_id=42,
        guide_instruction="환불 문의는 주문번호를 먼저 확인하세요.",
    )
    context = listener.AgentRunExecutionContext(
        run_id=1,
        message_id="msg-1",
        spec_id=1,
        spec=None,
        raw_spec=config.model_dump(mode="json"),
        user_input_values={},
        event=AgentWebhookEvent(
            event_id="evt-1",
            source="channel_talk",
            event_type="user_chat.created",
            payload={},
        ),
        global_context=Mock(),
    )
    monkeypatch.setattr(
        listener,
        "build_channel_talk_user_chat_inputs",
        AsyncMock(
            return_value={
                "channel_talk_user_chat_context": "결제가 안 돼요",
                "channel_talk_user_chat_id": "uc-1",
            }
        ),
    )

    result = await listener._build_automation_input(context)

    assert result is not None
    assert result.slack_channel_id == "C123"
    assert result.slack_credential_id == 42
    assert result.inquiry_text == "결제가 안 돼요"
    assert result.user_chat_id == "uc-1"
    assert result.guide_instruction == "환불 문의는 주문번호를 먼저 확인하세요."


@pytest.mark.asyncio
async def test_build_automation_input_returns_none_for_invalid_config(
    monkeypatch,
) -> None:
    context = listener.AgentRunExecutionContext(
        run_id=1,
        message_id="msg-1",
        spec_id=1,
        spec=None,
        raw_spec={"unexpected_field": "value"},
        user_input_values={},
        event=AgentWebhookEvent(
            event_id="evt-1",
            source="channel_talk",
            event_type="user_chat.created",
            payload={},
        ),
        global_context=Mock(),
    )
    monkeypatch.setattr(
        listener,
        "build_channel_talk_user_chat_inputs",
        AsyncMock(
            return_value={
                "channel_talk_user_chat_context": "안녕하세요",
                "channel_talk_user_chat_id": "uc-1",
            }
        ),
    )

    result = await listener._build_automation_input(context)

    assert result is None
