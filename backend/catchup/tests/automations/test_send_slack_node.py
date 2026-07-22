import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from catchup.automations.nodes.send_slack import send_slack_node


def _make_state(
    guide_text: str = "테스트 가이드",
    guide_explanation: str = "테스트 설명",
) -> dict:
    return {
        "inquiry_text": "결제 오류",
        "channel_talk_channel_id": "channel-001",
        "user_chat_id": "abc123",
        "slack_channel_id": "C123456",
        "slack_credential_id": 1,
        "guide_text": guide_text,
        "guide_explanation": guide_explanation,
        "citations": [
            {
                "index": 1,
                "title": "환불 정책",
                "url": "https://example.com/refund",
            }
        ],
    }


@pytest.mark.asyncio
async def test_send_slack_node_posts_thread_reply():
    """channel_talk 메시지를 찾아 스레드에 가이드를 발송한다."""
    state = _make_state()

    mock_token = MagicMock()
    mock_token.bot_access_token = "xoxb-test"
    mock_token.team_id = "T123"

    mock_client = AsyncMock()
    mock_client.get_conversation_history.return_value = {
        "messages": [
            {
                "ts": "1700000000.000000",
                "bot_id": "B123",
                "text": "https://example.com/user-chats/abc123",
            }
        ],
        "has_more": False,
    }
    mock_client.post_message = AsyncMock()

    with (
        patch(
            "catchup.automations.nodes.send_slack.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_token,
        ),
        patch(
            "catchup.automations.nodes.send_slack.SlackApiClientWrapper",
            return_value=mock_client,
        ),
    ):
        result = await send_slack_node(state)

    assert mock_client.post_message.await_count == 2
    explanation_call, guide_call = mock_client.post_message.await_args_list
    assert explanation_call.kwargs["channel"] == "C123456"
    assert explanation_call.kwargs["thread_ts"] == "1700000000.000000"
    assert "테스트 설명" in explanation_call.kwargs["text"]
    assert "환불 정책" in explanation_call.kwargs["text"]
    assert "테스트 가이드" in guide_call.kwargs["text"]
    button = guide_call.kwargs["blocks"][1]["elements"][0]
    assert json.loads(button["value"]) == {
        "channel_id": "channel-001",
        "user_chat_id": "abc123",
    }
    assert result == {}


@pytest.mark.asyncio
async def test_send_slack_node_no_guide_text_skips():
    """가이드와 설명이 모두 없으면 발송을 건너뛴다."""
    state = _make_state(guide_text="", guide_explanation="")
    state["citations"] = []

    with (
        patch("catchup.automations.nodes.send_slack.asyncio.to_thread") as mock_to_thread,
        patch("catchup.automations.nodes.send_slack.SlackApiClientWrapper") as mock_cls,
    ):
        result = await send_slack_node(state)

    mock_to_thread.assert_not_called()
    mock_cls.assert_not_called()
    assert result == {}


@pytest.mark.asyncio
async def test_send_slack_node_retries_until_link_message_appears():
    """Channel Talk 연동 메시지가 아직 없으면 backoff 후 재검색해 발송한다."""
    state = _make_state()

    mock_token = MagicMock()
    mock_token.bot_access_token = "xoxb-test"
    mock_token.team_id = "T123"

    not_found_response = {"messages": [], "has_more": False}
    found_response = {
        "messages": [
            {
                "ts": "1700000000.000000",
                "bot_id": "B123",
                "text": "https://example.com/user-chats/abc123",
            }
        ],
        "has_more": False,
    }

    mock_client = AsyncMock()
    mock_client.get_conversation_history.side_effect = [
        not_found_response,
        not_found_response,
        found_response,
    ]
    mock_client.post_message = AsyncMock()

    with (
        patch(
            "catchup.automations.nodes.send_slack.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_token,
        ),
        patch(
            "catchup.automations.nodes.send_slack.SlackApiClientWrapper",
            return_value=mock_client,
        ),
        patch(
            "catchup.automations.nodes.send_slack.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        result = await send_slack_node(state)

    assert mock_client.get_conversation_history.await_count == 3
    assert mock_sleep.await_count == 2
    assert mock_client.post_message.await_count == 2
    assert result == {}


@pytest.mark.asyncio
async def test_send_slack_node_retries_explanation_before_guide():
    """설명 전송이 실패하면 재시도하고 성공한 뒤 가이드를 전송한다."""
    state = _make_state()
    mock_token = MagicMock(bot_access_token="xoxb-test", team_id="T123")
    mock_client = AsyncMock()
    mock_client.get_conversation_history.return_value = {
        "messages": [
            {
                "ts": "1700000000.000000",
                "bot_id": "B123",
                "text": "https://example.com/user-chats/abc123",
            }
        ],
        "has_more": False,
    }
    mock_client.post_message.side_effect = [RuntimeError("temporary"), {}, {}]

    with (
        patch(
            "catchup.automations.nodes.send_slack.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_token,
        ),
        patch(
            "catchup.automations.nodes.send_slack.SlackApiClientWrapper",
            return_value=mock_client,
        ),
        patch(
            "catchup.automations.nodes.send_slack.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        await send_slack_node(state)

    assert mock_client.post_message.await_count == 3
    mock_sleep.assert_awaited_once_with(1.0)


@pytest.mark.asyncio
async def test_send_slack_node_does_not_send_guide_when_explanation_fails():
    """설명 재시도가 모두 실패하면 가이드는 전송하지 않는다."""
    state = _make_state()
    mock_token = MagicMock(bot_access_token="xoxb-test", team_id="T123")
    mock_client = AsyncMock()
    mock_client.get_conversation_history.return_value = {
        "messages": [
            {
                "ts": "1700000000.000000",
                "bot_id": "B123",
                "text": "https://example.com/user-chats/abc123",
            }
        ],
        "has_more": False,
    }
    mock_client.post_message.side_effect = RuntimeError("temporary")

    with (
        patch(
            "catchup.automations.nodes.send_slack.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_token,
        ),
        patch(
            "catchup.automations.nodes.send_slack.SlackApiClientWrapper",
            return_value=mock_client,
        ),
        patch(
            "catchup.automations.nodes.send_slack.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        pytest.raises(RuntimeError, match="temporary"),
    ):
        await send_slack_node(state)

    assert mock_client.post_message.await_count == 3
    assert all(
        call.kwargs["text"].startswith("테스트 설명")
        for call in mock_client.post_message.await_args_list
    )


@pytest.mark.asyncio
async def test_send_slack_node_raises_after_retries_exhausted():
    """재시도 횟수를 다 써도 못 찾으면 RuntimeError를 발생시킨다."""
    state = _make_state()

    mock_token = MagicMock()
    mock_token.bot_access_token = "xoxb-test"
    mock_token.team_id = "T123"

    mock_client = AsyncMock()
    mock_client.get_conversation_history.return_value = {
        "messages": [],
        "has_more": False,
    }
    mock_client.post_message = AsyncMock()

    with (
        patch(
            "catchup.automations.nodes.send_slack.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_token,
        ),
        patch(
            "catchup.automations.nodes.send_slack.SlackApiClientWrapper",
            return_value=mock_client,
        ),
        patch(
            "catchup.automations.nodes.send_slack.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        patch("catchup.automations.nodes.send_slack.logger") as mock_logger,
        pytest.raises(RuntimeError, match="not found for user_chat_id=abc123"),
    ):
        await send_slack_node(state)

    mock_logger.error.assert_called_once()
    error_call_kwargs = mock_logger.error.call_args.kwargs
    assert error_call_kwargs["user_chat_id"] == "abc123"
    assert error_call_kwargs["channel_id"] == "C123456"

    mock_client.post_message.assert_not_awaited()
