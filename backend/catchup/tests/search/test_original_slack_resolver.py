from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

import pytest

from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.connectors.slack.client import SlackRateLimitError
from catchup.db.models import SourceType
from catchup.search.original.ids import OriginalDocumentRef
from catchup.search.original.resolvers.slack import SlackOriginalError
from catchup.search.original.resolvers.slack import SlackOriginalResolver
from catchup.server.search.schemas import OriginalContentRequest


class _FakeSlackClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def get_conversation_replies(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


class _FailingSlackClient:
    def __init__(self, exc: Exception):
        self.exc = exc

    async def get_conversation_replies(self, **kwargs):
        del kwargs
        raise self.exc


class _FakeSlackClientFactory:
    def __init__(self, client: _FakeSlackClient):
        self.client = client
        self.calls = []

    def __call__(self, access_token: str, team_id: str) -> _FakeSlackClient:
        self.calls.append((access_token, team_id))
        return self.client


class _FakeSlackRepositories:
    def __init__(self):
        self.token_calls = []
        self.workspace_calls = []
        self.channel_calls = []
        self.users_calls = []

    def token_lookup(self, db, team_id):
        self.token_calls.append((db, team_id))
        return SimpleNamespace(bot_access_token="xoxb-db-token")

    def workspace_lookup(self, db, team_id):
        self.workspace_calls.append((db, team_id))
        return SimpleNamespace(domain="catchup--hq")

    def channel_lookup(self, db, channel_id):
        self.channel_calls.append((db, channel_id))
        return SimpleNamespace(name="general")

    def users_lookup(self, db, team_id, user_ids):
        self.users_calls.append((db, team_id, user_ids))
        return {
            "U1": SimpleNamespace(
                user_id="U1",
                name="parent",
                display_name="Parent User",
                avatar_url="https://example.com/u1.png",
            ),
            "U2": SimpleNamespace(
                user_id="U2",
                name="reply",
                display_name="Reply User",
                avatar_url=None,
            ),
        }


@pytest.mark.asyncio
async def test_slack_resolver_fetches_replies_once_and_returns_raw_payload() -> None:
    slack_payload = {
        "ok": True,
        "messages": [
            {
                "type": "message",
                "user": "U1",
                "text": "parent text",
                "ts": "1716400000.000100",
                "blocks": [{"type": "rich_text"}],
            },
            {
                "type": "message",
                "user": "U2",
                "text": "reply text",
                "ts": "1716400001.000200",
            },
        ],
        "has_more": True,
        "response_metadata": {"next_cursor": "cursor-2"},
    }
    fake_client = _FakeSlackClient(slack_payload)
    fake_repositories = _FakeSlackRepositories()
    resolver = SlackOriginalResolver(
        bot_access_token="xoxb-test",
        client_factory=lambda access_token, team_id: fake_client,
        workspace_lookup=fake_repositories.workspace_lookup,
        channel_lookup=fake_repositories.channel_lookup,
        users_lookup=fake_repositories.users_lookup,
        clock=lambda: datetime(2026, 5, 24, tzinfo=timezone.utc),
    )
    request = OriginalContentRequest(
        connector=SourceType.SLACK,
        document_id="slack:message:T1:C1:1716400000.000100",
        next_cursor="cursor-1",
    )
    ref = OriginalDocumentRef(
        connector=SourceType.SLACK,
        entity_type="message",
        document_id=request.document_id,
        identifiers={
            "team_id": "T1",
            "channel_id": "C1",
            "ts": "1716400000.000100",
        },
    )

    response = await resolver.resolve(request=request, ref=ref, db=object())

    assert fake_client.calls == [
        {
            "channel": "C1",
            "ts": "1716400000.000100",
            "cursor": "cursor-1",
            "limit": 200,
        }
    ]
    assert response.connector == SourceType.SLACK
    assert response.entity_type == "message"
    assert response.document_id == request.document_id
    assert response.title == "parent text"
    assert response.url == (
        "https://catchup--hq.slack.com/archives/C1/p1716400000000100"
    )
    assert response.next_cursor == "cursor-2"
    assert response.metadata["team_id"] == "T1"
    assert response.metadata["channel_id"] == "C1"
    assert response.metadata["thread_ts"] == "1716400000.000100"
    assert len(response.items) == 1
    item = response.items[0]
    assert item.id == "1716400000.000100"
    assert item.type == "slack_conversations_replies_raw"
    assert item.raw_payload == slack_payload
    assert not hasattr(item, "contents")


@pytest.mark.asyncio
async def test_slack_resolver_loads_token_and_only_message_users_from_db() -> None:
    slack_payload = {
        "ok": True,
        "messages": [
            {
                "type": "message",
                "user": "U1",
                "text": "parent text",
                "ts": "1716400000.000100",
                "reply_users": ["U2"],
            },
            {
                "type": "message",
                "user": "U2",
                "parent_user_id": "U1",
                "text": "reply text",
                "ts": "1716400001.000200",
            },
        ],
    }
    fake_client = _FakeSlackClient(slack_payload)
    fake_client_factory = _FakeSlackClientFactory(fake_client)
    fake_repositories = _FakeSlackRepositories()
    db = object()
    resolver = SlackOriginalResolver(
        client_factory=fake_client_factory,
        token_lookup=fake_repositories.token_lookup,
        workspace_lookup=fake_repositories.workspace_lookup,
        channel_lookup=fake_repositories.channel_lookup,
        users_lookup=fake_repositories.users_lookup,
        clock=lambda: datetime(2026, 5, 24, tzinfo=timezone.utc),
    )
    request = OriginalContentRequest(
        connector=SourceType.SLACK,
        document_id="slack:message:T1:C1:1716400000.000100",
    )
    ref = OriginalDocumentRef(
        connector=SourceType.SLACK,
        entity_type="message",
        document_id=request.document_id,
        identifiers={
            "team_id": "T1",
            "channel_id": "C1",
            "ts": "1716400000.000100",
        },
    )

    response = await resolver.resolve(request=request, ref=ref, db=db)

    assert fake_repositories.token_calls == [(db, "T1")]
    assert fake_client_factory.calls == [("xoxb-db-token", "T1")]
    assert fake_repositories.workspace_calls == [(db, "T1")]
    assert fake_repositories.channel_calls == [(db, "C1")]
    assert fake_repositories.users_calls == [(db, "T1", ["U1", "U2"])]
    assert response.metadata == {
        "team_id": "T1",
        "channel_id": "C1",
        "thread_ts": "1716400000.000100",
        "users_by_id": {
            "U1": {
                "id": "U1",
                "name": "parent",
                "display_name": "Parent User",
                "profile_image_url": "https://example.com/u1.png",
            },
            "U2": {
                "id": "U2",
                "name": "reply",
                "display_name": "Reply User",
                "profile_image_url": None,
            },
        },
        "channel_name": "general",
        "workspace_domain": "catchup--hq",
    }
    assert "cache_misses" not in response.metadata


@pytest.mark.parametrize(
    ("exc", "status_code"),
    [
        (
            SlackConnectorApiError(
                "Slack API error",
                status_code=200,
                metadata={"error": "invalid_cursor"},
            ),
            400,
        ),
        (
            SlackConnectorApiError(
                "Slack API error",
                status_code=200,
                metadata={"error": "invalid_auth"},
            ),
            401,
        ),
        (
            SlackConnectorApiError(
                "Slack API error",
                status_code=200,
                metadata={"error": "channel_not_found"},
            ),
            404,
        ),
        (
            SlackConnectorApiError(
                "Slack API error",
                status_code=200,
                metadata={"error": "missing_scope"},
            ),
            403,
        ),
        (
            SlackConnectorApiError(
                "Slack API access denied",
                status_code=200,
                metadata={"error": "team_access_not_granted"},
            ),
            403,
        ),
        (
            SlackRateLimitError("Slack API rate limited", retry_after=1),
            429,
        ),
        (
            SlackConnectorApiError(
                "Slack API unavailable",
                status_code=503,
                metadata={"error": "server_error"},
            ),
            502,
        ),
    ],
)
@pytest.mark.asyncio
async def test_slack_resolver_maps_slack_api_errors_to_original_errors(
    exc: Exception,
    status_code: int,
) -> None:
    resolver = SlackOriginalResolver(
        bot_access_token="xoxb-test",
        client_factory=lambda access_token, team_id: _FailingSlackClient(exc),
        clock=lambda: datetime(2026, 5, 24, tzinfo=timezone.utc),
    )
    request = OriginalContentRequest(
        connector=SourceType.SLACK,
        document_id="slack:message:T1:C1:1716400000.000100",
    )
    ref = OriginalDocumentRef(
        connector=SourceType.SLACK,
        entity_type="message",
        document_id=request.document_id,
        identifiers={
            "team_id": "T1",
            "channel_id": "C1",
            "ts": "1716400000.000100",
        },
    )

    with pytest.raises(SlackOriginalError) as error:
        await resolver.resolve(request=request, ref=ref)

    assert error.value.status_code == status_code
