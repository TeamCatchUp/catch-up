from __future__ import annotations

from unittest import IsolatedAsyncioTestCase

import httpx

from catchup.connectors.channel_talk.client import ChannelTalkApiClient
from catchup.connectors.channel_talk.exceptions import ChannelTalkPayloadError
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatState


class ChannelTalkFullSyncClientTests(IsolatedAsyncioTestCase):
    async def test_list_user_chats_parses_page_and_quota_snapshot(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/open/v5/user-chats")
            self.assertEqual(request.url.params["state"], "opened")
            self.assertEqual(request.url.params["since"], "cursor-1")

            return httpx.Response(
                200,
                json={
                    "userChats": [
                        {
                            "id": "chat-1",
                            "state": "opened",
                            "updatedAt": "2026-04-21T09:00:00Z",
                            "userId": "user-1",
                            "memberId": "member-1",
                            "ignoredField": "ignored",
                        },
                        {
                            "id": "chat-2",
                            "user": {
                                "id": "user-2",
                                "memberId": "member-2",
                            },
                        },
                    ],
                    "next": "cursor-2",
                },
                headers={
                    "x-ratelimit-limit": "40",
                    "x-ratelimit-remaining": "39",
                    "retry-after": "7",
                    "x-ratelimit-reset": "1776765600",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chats(
                access_key="access-key",
                access_secret="access-secret",
                state="opened",
                since="cursor-1",
            )

        self.assertEqual(page.next_cursor, "cursor-2")
        self.assertEqual(len(page.items), 2)
        self.assertEqual(page.items[0].user_chat_id, "chat-1")
        self.assertEqual(page.items[0].state, ChannelTalkUserChatState.OPENED)
        self.assertEqual(page.items[0].user_id, "user-1")
        self.assertEqual(page.items[0].member_id, "member-1")
        self.assertEqual(page.items[1].state, ChannelTalkUserChatState.OPENED)
        self.assertEqual(page.items[1].user_id, "user-2")
        self.assertEqual(page.items[1].member_id, "member-2")
        self.assertEqual(page.quota_snapshot.limit, 40)
        self.assertEqual(page.quota_snapshot.remaining, 39)
        self.assertEqual(page.quota_snapshot.retry_after_seconds, 7)
        self.assertTrue(page.quota_snapshot.source_headers_present)

    async def test_list_user_chats_supports_list_payload_without_headers(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "chat-3",
                        "createdAt": "2026-04-21T10:00:00Z",
                        "userId": "user-3",
                    }
                ],
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chats(
                access_key="access-key",
                access_secret="access-secret",
                state="closed",
            )

        self.assertIsNone(page.next_cursor)
        self.assertEqual(
            set(page.items[0].model_dump().keys()),
            {"ordering_marker", "user_id", "user_chat_id", "member_id", "state"},
        )
        self.assertFalse(page.quota_snapshot.source_headers_present)

    async def test_list_user_chats_matches_root_users_by_user_id(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "userChats": [
                        {
                            "id": "chat-users-1",
                            "updatedAt": "2026-04-21T10:30:00Z",
                            "userId": "user-from-users",
                        }
                    ],
                    "users": [
                        {
                            "id": "user-other",
                            "memberId": "member-other",
                        },
                        {
                            "id": "user-from-users",
                            "memberId": "member-from-users",
                        }
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chats(
                access_key="access-key",
                access_secret="access-secret",
                state="opened",
            )

        self.assertEqual(page.items[0].user_id, "user-from-users")
        self.assertEqual(page.items[0].member_id, "member-from-users")

    async def test_list_user_chats_does_not_guess_identity_from_ambiguous_root_users(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "userChats": [
                        {"id": "chat-1"},
                        {"id": "chat-2"},
                    ],
                    "users": [
                        {"id": "user-a", "memberId": "member-a"},
                        {"id": "user-b", "memberId": "member-b"},
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chats(
                access_key="access-key",
                access_secret="access-secret",
                state="opened",
            )

        self.assertIsNone(page.items[0].user_id)
        self.assertIsNone(page.items[0].member_id)
        self.assertIsNone(page.items[1].user_id)
        self.assertIsNone(page.items[1].member_id)

    async def test_list_user_chats_accepts_opened_closed_and_snoozed_sweep_inputs(self) -> None:
        seen_states: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            seen_states.append(request.url.params["state"])
            return httpx.Response(
                200,
                json={"userChats": [{"id": f"chat-{request.url.params['state']}"}]},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            for state in ChannelTalkUserChatState:
                page = await client.list_user_chats(
                    access_key="access-key",
                    access_secret="access-secret",
                    state=state,
                )
                self.assertEqual(page.items[0].state, state)

        self.assertEqual(seen_states, ["opened", "closed", "snoozed"])

    async def test_list_user_chats_defaults_sort_order_to_desc(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["sortOrder"], "desc")
            return httpx.Response(
                200,
                json={"userChats": [{"id": "chat-default-order"}]},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            await client.list_user_chats(
                access_key="access-key",
                access_secret="access-secret",
                state="opened",
            )

    async def test_get_user_chat_parses_detail_payload_for_later_document_build(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/open/v5/user-chats/chat-123")
            return httpx.Response(
                200,
                json={
                    "id": "chat-123",
                    "channelId": "channel-123",
                    "state": "opened",
                    "managed": True,
                    "priority": "urgent",
                    "name": "VIP onboarding",
                    "goalState": "resolved",
                    "userId": "user-123",
                    "managers": [
                        {
                            "id": "manager-1",
                            "name": "Agent Lee",
                            "email": "lee@example.com",
                            "roleId": "role-1",
                        }
                    ],
                    "assignee": {
                        "id": "manager-1",
                        "name": "Agent Lee",
                        "email": "lee@example.com",
                    },
                    "firstAssigneeIdAfterOpen": "manager-2",
                    "tags": [
                        {"key": "vip", "name": "VIP"},
                        "renewal",
                    ],
                    "frontMessageId": "front-1",
                    "deskMessageId": "desk-1",
                    "userLastMessageId": "user-msg-1",
                    "createdAt": "2026-04-20T09:00:00Z",
                    "updatedAt": "2026-04-21T09:00:00Z",
                    "openedAt": "2026-04-20T09:01:00Z",
                    "closedAt": "2026-04-21T11:00:00Z",
                    "waitingTime": 12,
                    "avgReplyTime": 34,
                    "replyCount": 2,
                    "user": {
                        "id": "user-123",
                        "memberId": "member-123",
                        "name": "Customer Kim",
                        "email": "kim@example.com",
                        "profile": {"name": "Customer Kim"},
                    }
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            detail = await client.get_user_chat(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
            )

        self.assertEqual(detail.user_chat_id, "chat-123")
        self.assertEqual(detail.channel_id, "channel-123")
        self.assertEqual(detail.state, ChannelTalkUserChatState.OPENED)
        self.assertTrue(detail.managed)
        self.assertEqual(detail.customer.external_user_id, "user-123")
        self.assertEqual(detail.customer.member_id, "member-123")
        self.assertEqual(detail.assignment.manager_ids, ("manager-1",))
        self.assertEqual(detail.assignment.assignee_id, "manager-1")
        self.assertEqual(detail.assignment.first_assignee_id_after_open, "manager-2")
        self.assertEqual([tag.name for tag in detail.tags], ["VIP", "renewal"])
        self.assertEqual(detail.anchors.front_message_id, "front-1")
        self.assertEqual(detail.metrics.avg_reply_time, 34)
        self.assertEqual(detail.metrics.reply_count, 2)
        self.assertIsNotNone(detail.raw_payload)

    async def test_get_user_chat_does_not_treat_chat_id_as_customer_id_when_customer_is_missing(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "chat-456",
                    "channelId": "channel-123",
                    "state": "closed",
                    "updatedAt": "2026-04-21T09:00:00Z",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            detail = await client.get_user_chat(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-456",
            )

        self.assertEqual(detail.user_chat_id, "chat-456")
        self.assertIsNone(detail.customer)

    async def test_get_user_chat_filters_relevant_managers_from_lookup_tables(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "userChat": {
                        "id": "chat-789",
                        "state": "opened",
                        "managerIds": ["manager-2"],
                        "assignee": {
                            "id": "manager-1",
                            "name": "Agent One",
                        },
                        "firstAssigneeIdAfterOpen": "manager-3",
                    },
                    "managers": [
                        {"id": "manager-1", "name": "Agent One"},
                        {"id": "manager-2", "name": "Agent Two"},
                        {"id": "manager-3", "name": "Agent Three"},
                        {"id": "manager-9", "name": "Unrelated"},
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            detail = await client.get_user_chat(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-789",
            )

        self.assertEqual(detail.assignment.manager_ids, ("manager-2", "manager-1"))
        self.assertEqual(
            [manager.manager_id for manager in detail.assignment.managers],
            ["manager-2", "manager-1"],
        )

    async def test_get_user_chat_uses_scalar_assignee_id_as_actual_assignee_identity(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "userChat": {
                        "id": "chat-live-shape",
                        "channelId": "channel-123",
                        "state": "opened",
                        "managerIds": ["manager-1"],
                        "assigneeId": "manager-1",
                        "firstAssigneeIdAfterOpen": "manager-1",
                        "firstAskedAt": "2026-04-21T09:00:00Z",
                    },
                    "user": {
                        "id": "user-123",
                        "memberId": "member-123",
                    },
                    "managers": [
                        {
                            "id": "manager-1",
                            "name": "Agent Live",
                            "email": "live@example.com",
                        }
                    ],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            detail = await client.get_user_chat(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-live-shape",
            )

        self.assertEqual(detail.assignment.assignee_id, "manager-1")
        self.assertEqual(detail.assignment.assignee_name, "Agent Live")
        self.assertEqual(detail.assignment.assignee_email, "live@example.com")
        self.assertEqual(detail.assignment.manager_ids, ("manager-1",))
        self.assertEqual(detail.assignment.first_assignee_id_after_open, "manager-1")
        self.assertEqual(detail.timing.first_asked_at.isoformat(), "2026-04-21T09:00:00+00:00")

    async def test_list_user_chat_messages_parses_messages_and_pagination(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/open/v5/user-chats/chat-123/messages")
            self.assertEqual(request.url.params["since"], "cursor-10")
            self.assertEqual(request.url.params["sortOrder"], "asc")
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-1",
                            "userChatId": "chat-123",
                            "type": "chat",
                            "personType": "manager",
                            "manager": {
                                "id": "manager-1",
                                "name": "Agent Lee",
                                "email": "lee@example.com",
                                "roleId": "role-1",
                            },
                            "plainText": "Hello from support",
                            "createdAt": "2026-04-21T09:00:00Z",
                            "updatedAt": "2026-04-21T09:01:00Z",
                            "files": [
                                {
                                    "key": "file-1",
                                    "name": "guide.pdf",
                                    "contentType": "application/pdf",
                                    "size": 1024,
                                }
                            ],
                            "buttons": [
                                {
                                    "text": "Open",
                                    "action": "url",
                                    "url": "https://example.com",
                                }
                            ],
                            "blocks": [
                                {
                                    "type": "paragraph",
                                    "text": "Hello from support",
                                }
                            ],
                        },
                        {
                            "id": "msg-2",
                            "type": "note",
                            "personType": "customer",
                            "user": {
                                "id": "user-123",
                                "memberId": "member-123",
                                "name": "Customer Kim",
                            },
                            "text": "Thanks!",
                            "private": True,
                            "createdAt": "2026-04-21T09:05:00Z",
                        },
                    ],
                    "next": "cursor-11",
                },
                headers={
                    "x-rate-limit-remaining": "998",
                    "x-rate-limit-limit": "1000",
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chat_messages(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
                since="cursor-10",
                sort_order="asc",
            )

        self.assertEqual(page.next_cursor, "cursor-11")
        self.assertEqual(len(page.messages), 2)
        self.assertEqual(page.messages[0].message_id, "msg-1")
        self.assertEqual(page.messages[0].author.author_type, "manager")
        self.assertEqual(page.messages[0].author.manager_id, "manager-1")
        self.assertEqual(page.messages[0].attachments[0].file_key, "file-1")
        self.assertEqual(page.messages[0].buttons[0].url, "https://example.com")
        self.assertEqual(page.messages[0].blocks[0].block_type, "paragraph")
        self.assertEqual(page.messages[1].user_chat_id, "chat-123")
        self.assertEqual(page.messages[1].author.user_id, "user-123")
        self.assertTrue(page.messages[1].is_private)
        self.assertEqual(page.quota_snapshot.limit, 1000)
        self.assertEqual(page.quota_snapshot.remaining, 998)

    async def test_list_user_chat_messages_maps_bare_manager_person_id_to_manager_identity(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-live-manager",
                            "chatId": "chat-123",
                            "personType": "manager",
                            "personId": "manager-612148",
                            "plainText": "답변드립니다.",
                            "createdAt": "2026-04-21T09:00:00Z",
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chat_messages(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
            )

        self.assertEqual(page.messages[0].author.author_type, "manager")
        self.assertEqual(page.messages[0].author.manager_id, "manager-612148")
        self.assertIsNone(page.messages[0].author.user_id)

    async def test_list_user_chat_messages_maps_bare_user_person_id_to_user_identity(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-live-user",
                            "chatId": "chat-123",
                            "personType": "user",
                            "personId": "user-69df207a",
                            "plainText": "문의드립니다.",
                            "createdAt": "2026-04-21T09:00:00Z",
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chat_messages(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
            )

        self.assertEqual(page.messages[0].author.author_type, "user")
        self.assertEqual(page.messages[0].author.user_id, "user-69df207a")
        self.assertIsNone(page.messages[0].author.manager_id)

    async def test_list_user_chat_messages_defaults_sort_order_to_desc(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["sortOrder"], "desc")
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-1",
                            "userChatId": "chat-123",
                            "createdAt": "2026-04-21T09:00:00Z",
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            await client.list_user_chat_messages(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
            )

    async def test_list_user_chat_messages_treats_private_option_as_private_message(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-private-option",
                            "type": "note",
                            "userChatId": "chat-123",
                            "options": ["private"],
                            "createdAt": "2026-04-21T09:05:00Z",
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chat_messages(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
            )

        self.assertTrue(page.messages[0].is_private)

    async def test_list_user_chat_messages_preserves_inline_bot_identity_without_root_lookup(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-bot-inline",
                            "type": "chat",
                            "userChatId": "chat-123",
                            "personType": "bot",
                            "personId": "bot-inline-1",
                            "botName": "Reminder Bot",
                            "createdAt": "2026-04-21T09:10:00Z",
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chat_messages(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
            )

        self.assertEqual(page.messages[0].author.bot_id, "bot-inline-1")
        self.assertEqual(page.messages[0].author.bot_name, "Reminder Bot")
        self.assertEqual(page.messages[0].author.name, "Reminder Bot")

    async def test_list_user_chat_messages_recovers_bot_author_from_root_bots_collection(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-bot-1",
                            "type": "chat",
                            "userChatId": "chat-123",
                            "personType": "bot",
                            "personId": "bot-42",
                            "plainText": "Automated reply",
                            "createdAt": "2026-04-21T09:10:00Z",
                        }
                    ],
                    "bots": [
                        {
                            "id": "bot-42",
                            "name": "Workflow Bot",
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chat_messages(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
            )

        self.assertEqual(page.messages[0].author.author_type, "bot")
        self.assertEqual(page.messages[0].author.bot_id, "bot-42")
        self.assertEqual(page.messages[0].author.bot_name, "Workflow Bot")
        self.assertEqual(page.messages[0].author.name, "Workflow Bot")
        self.assertTrue(page.messages[0].author.is_bot)

    async def test_list_user_chat_messages_parses_structured_log_form_and_web_page_payloads(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-log",
                            "userChatId": "chat-123",
                            "type": "event",
                            "log": {
                                "action": "chat_closed",
                                "type": "system",
                                "name": "Channel Talk",
                            },
                            "createdAt": "2026-04-21T09:05:00Z",
                        },
                        {
                            "id": "msg-form",
                            "userChatId": "chat-123",
                            "type": "form",
                            "form": {
                                "type": "contact",
                                "submittedAt": "2026-04-21T09:06:00Z",
                                "inputs": [
                                    {
                                        "label": "Email",
                                        "type": "text",
                                        "value": {"text": "user@example.com"},
                                    }
                                ],
                            },
                            "createdAt": "2026-04-21T09:06:00Z",
                        },
                        {
                            "id": "msg-web",
                            "userChatId": "chat-123",
                            "type": "card",
                            "webPage": {
                                "title": "Docs",
                                "url": "https://example.com/docs",
                                "publisher": "Example",
                            },
                            "createdAt": "2026-04-21T09:07:00Z",
                        },
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            page = await client.list_user_chat_messages(
                access_key="access-key",
                access_secret="access-secret",
                user_chat_id="chat-123",
            )

        self.assertEqual(page.messages[0].log.action, "chat_closed")
        self.assertEqual(page.messages[0].plain_text, "chat_closed")
        self.assertEqual(page.messages[1].form.form_type, "contact")
        self.assertEqual(page.messages[1].form.inputs[0].value, "user@example.com")
        self.assertEqual(page.messages[1].plain_text, "Email: user@example.com")
        self.assertEqual(page.messages[2].web_page.title, "Docs")
        self.assertEqual(page.messages[2].plain_text, "Docs\nhttps://example.com/docs")

    async def test_list_user_chat_messages_rejects_payload_user_chat_id_mismatch(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "id": "msg-1",
                            "userChatId": "chat-other",
                            "createdAt": "2026-04-21T09:00:00Z",
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.channel.io",
        ) as http_client:
            client = ChannelTalkApiClient(http_client=http_client)
            with self.assertRaisesRegex(
                ChannelTalkPayloadError,
                "invalid user chat message list payload",
            ):
                await client.list_user_chat_messages(
                    access_key="access-key",
                    access_secret="access-secret",
                    user_chat_id="chat-123",
                )
