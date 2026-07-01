from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from catchup.automations.nodes.send_slack import send_slack_node


def _make_state(guide_text: str = "테스트 가이드") -> dict:
    return {
        "inquiry_text": "결제 오류",
        "user_chat_id": "abc123",
        "slack_channel_id": "C123456",
        "slack_credential_id": 1,
        "guide_text": guide_text,
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

    mock_client.post_message.assert_awaited_once()
    call_kwargs = mock_client.post_message.call_args.kwargs
    assert call_kwargs["channel"] == "C123456"
    assert call_kwargs["thread_ts"] == "1700000000.000000"
    assert "테스트 가이드" in call_kwargs["text"]
    assert result == {}


@pytest.mark.asyncio
async def test_send_slack_node_no_guide_text_skips():
    """guide_text가 없으면 발송을 건너뛴다."""
    state = _make_state(guide_text="")

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
    mock_client.post_message.assert_awaited_once()
    assert result == {}


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
