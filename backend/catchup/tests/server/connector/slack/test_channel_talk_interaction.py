import asyncio
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from catchup.automations.channel_talk_actions import CHANNEL_TALK_SEND_ACTION_ID
from catchup.automations.channel_talk_actions import CHANNEL_TALK_SEND_MODAL_CALLBACK_ID
from catchup.automations.channel_talk_actions import ChannelTalkActionPayload
from catchup.automations.channel_talk_actions import ChannelTalkMessageMode
from catchup.automations.channel_talk_actions import ChannelTalkModalContext
from catchup.automations.channel_talk_actions import ChannelTalkSubmission
from catchup.automations.channel_talk_actions import serialize_action_payload
from catchup.automations.channel_talk_actions import serialize_modal_context
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.server.connector.slack import interaction_handler
from catchup.server.connector.slack.schemas import SlackWebhookRequest


def _request(event: dict, *, wrapper_type: str) -> SlackWebhookRequest:
    return SlackWebhookRequest.from_raw(
        wrapper_type=wrapper_type,
        team_id="T123",
        event=event,
    )


@pytest.mark.asyncio
async def test_channel_talk_button_opens_prefilled_modal():
    slack_client = AsyncMock()
    request = _request(
        {
            "type": "block_actions",
            "trigger_id": "trigger-1",
            "user": {"id": "U123"},
            "channel": {"id": "C123"},
            "message": {"text": "초안 답변", "thread_ts": "1700.1"},
            "actions": [
                {
                    "action_id": CHANNEL_TALK_SEND_ACTION_ID,
                    "value": serialize_action_payload(
                        ChannelTalkActionPayload(
                            channel_id="channel-1",
                            user_chat_id="chat-1",
                        )
                    ),
                }
            ],
        },
        wrapper_type="block_actions",
    )

    with patch.object(
        interaction_handler,
        "_build_slack_client_sync",
        return_value=slack_client,
    ):
        await interaction_handler.handle_block_actions(request=request)

    view = slack_client.open_view.await_args.kwargs["view"]
    assert view["callback_id"] == CHANNEL_TALK_SEND_MODAL_CALLBACK_ID
    assert view["submit"]["text"] == "전송하기"
    assert view["blocks"][1]["element"]["initial_value"] == "초안 답변"
    assert [
        option["value"] for option in view["blocks"][0]["element"]["options"]
    ] == ["private", "actAsManager"]


@pytest.mark.asyncio
async def test_channel_talk_modal_submission_uses_edited_text():
    context = ChannelTalkModalContext(
        channel_id="channel-1",
        user_chat_id="chat-1",
        slack_channel_id="C123",
        slack_user_id="U123",
        thread_ts="1700.1",
    )
    request = _request(
        {
            "type": "view_submission",
            "view": {
                "callback_id": CHANNEL_TALK_SEND_MODAL_CALLBACK_ID,
                "private_metadata": serialize_modal_context(context),
                "state": {
                    "values": {
                        "channel_talk_message_mode": {
                            "channel_talk_message_mode_select": {
                                "selected_option": {"value": "private"}
                            }
                        },
                        "channel_talk_message": {
                            "channel_talk_message_input": {"value": "수정한 답변"}
                        },
                    }
                },
            },
        },
        wrapper_type="view_submission",
    )

    with patch.object(
        interaction_handler,
        "_complete_channel_talk_submission",
        new_callable=AsyncMock,
    ) as complete:
        response = await interaction_handler.handle_view_submission(request=request)
        await asyncio.sleep(0)

    assert response == {"response_action": "clear"}
    complete.assert_awaited_once_with(
        request=request,
        context=context,
        submission=ChannelTalkSubmission(
            mode=ChannelTalkMessageMode.PRIVATE,
            message="수정한 답변",
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "method_name"),
    [
        (ChannelTalkMessageMode.PRIVATE, "send_internal_user_chat_message"),
        (ChannelTalkMessageMode.ACT_AS_MANAGER, "send_user_chat_message_as_manager"),
    ],
)
async def test_channel_talk_submission_resolves_credentials_by_channel_id(
    mode: ChannelTalkMessageMode,
    method_name: str,
):
    request = _request({}, wrapper_type="view_submission")
    context = ChannelTalkModalContext(
        channel_id="channel-1",
        user_chat_id="chat-1",
        slack_channel_id="C123",
        slack_user_id="U123",
        thread_ts="1700.1",
    )
    credential = ChannelTalkCredentialsRecord(
        channel_id="channel-1",
        channel_name="고객센터",
        access_key="access-key",
        access_secret="access-secret",
    )
    channel_talk_client = AsyncMock()

    with (
        patch.object(
            interaction_handler,
            "_load_channel_talk_credential_sync",
            return_value=credential,
        ) as load_credential,
        patch.object(
            interaction_handler,
            "ChannelTalkCoreApiClient",
            return_value=channel_talk_client,
        ),
        patch.object(
            interaction_handler,
            "_post_channel_talk_submission_notice",
            new_callable=AsyncMock,
        ),
    ):
        await interaction_handler._complete_channel_talk_submission(
            request=request,
            context=context,
            submission=ChannelTalkSubmission(mode=mode, message="최종 답변"),
        )

    load_credential.assert_called_once_with("channel-1")
    getattr(channel_talk_client, method_name).assert_awaited_once_with(
        "access-key",
        "access-secret",
        channel_id="channel-1",
        user_chat_id="chat-1",
        message="최종 답변",
    )
