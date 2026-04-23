from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.channel_talk.full_sync_helper import (
    CHANNEL_TALK_FULL_SYNC_TARGET_ID,
)
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.db.models import SyncConnector
from catchup.server.sync.api import router
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncDispatchStatus

CHANNEL_ID = "channel-123"


def _build_connection_record(
    *,
    channel_id: str = CHANNEL_ID,
) -> ChannelTalkCredentialsRecord:
    return ChannelTalkCredentialsRecord(
        channel_id=channel_id,
        channel_name="Support",
        access_key="access-key",
        access_secret="access-secret",
        webhook_token="webhook-token",
    )


class _StubFullSyncService:
    def __init__(self) -> None:
        self.calls: list[tuple[SyncConnector, object]] = []

    async def dispatch(self, *, connector, request):
        self.calls.append((connector, request))
        return SyncDispatchResult(
            status=SyncDispatchStatus.ACCEPTED,
            connector=connector,
            scope_id=request.scope_id,
            job_id="job-123",
            event_ids=["event-123"],
            total_targets=1,
            queued_targets=1,
        )


class ChannelTalkSyncApiTests(TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[require_admin_user] = lambda: object()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_get_targets_returns_exact_singleton_channel_talk_bootstrap_target(self) -> None:
        with patch(
            "catchup.sync.query_service.load_channel_talk_connection",
            return_value=_build_connection_record(),
        ):
            response = self.client.get(
                "/api/v1/sync/targets",
                params={
                    "connector": "channel_talk",
                    "scope_id": CHANNEL_ID,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "connector": "channel_talk",
                "scope_id": CHANNEL_ID,
                "total_targets": 1,
                "targets": [
                    {
                        "target_id": CHANNEL_TALK_FULL_SYNC_TARGET_ID,
                        "display_name": "UserChat",
                        "target_type": "resource",
                        "is_accessible": True,
                        "metadata": {
                            "runtime_target_kind": "bootstrap",
                            "boundary": "tenant",
                            "target": CHANNEL_TALK_FULL_SYNC_TARGET_ID,
                            "stage": CHANNEL_TALK_FULL_SYNC_TARGET_ID,
                            "channel_id": CHANNEL_ID,
                        },
                    }
                ],
            },
        )

    def test_get_targets_rejects_blank_scope_id(self) -> None:
        response = self.client.get(
            "/api/v1/sync/targets",
            params={
                "connector": "channel_talk",
                "scope_id": " ",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertEqual(
            response.json()["detail"]["message"],
            "channel_talk channel_id(scope_id) is empty",
        )

    def test_get_targets_rejects_missing_channel_talk_connection(self) -> None:
        with patch(
            "catchup.sync.query_service.load_channel_talk_connection",
            return_value=None,
        ):
            response = self.client.get(
                "/api/v1/sync/targets",
                params={
                    "connector": "channel_talk",
                    "scope_id": CHANNEL_ID,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertEqual(
            response.json()["detail"]["message"],
            "channel_talk is not connected",
        )

    def test_get_targets_rejects_requested_channel_mismatch(self) -> None:
        with patch(
            "catchup.sync.query_service.load_channel_talk_connection",
            return_value=_build_connection_record(channel_id="channel-other"),
        ):
            response = self.client.get(
                "/api/v1/sync/targets",
                params={
                    "connector": "channel_talk",
                    "scope_id": CHANNEL_ID,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertEqual(
            response.json()["detail"]["message"],
            "Stored Channel Talk credentials do not match the requested channel",
        )

    def test_post_full_accepts_channel_talk_with_existing_shared_request_shape(self) -> None:
        stub_service = _StubFullSyncService()

        with patch(
            "catchup.server.sync.api.get_full_sync_service",
            return_value=stub_service,
        ):
            response = self.client.post(
                "/api/v1/sync/full",
                json={
                    "connector": "channel_talk",
                    "scope_id": CHANNEL_ID,
                    "target_ids": [CHANNEL_TALK_FULL_SYNC_TARGET_ID],
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json(),
            {
                "status": "accepted",
                "connector": "channel_talk",
                "scope_id": CHANNEL_ID,
                "job_id": "job-123",
                "event_ids": ["event-123"],
                "total_targets": 1,
                "queued_targets": 1,
                "message": None,
            },
        )
        self.assertEqual(len(stub_service.calls), 1)
        connector, dispatch_request = stub_service.calls[0]
        self.assertEqual(connector, SyncConnector.CHANNEL_TALK)
        self.assertEqual(dispatch_request.scope_id, CHANNEL_ID)
        self.assertEqual(
            dispatch_request.target_ids,
            [CHANNEL_TALK_FULL_SYNC_TARGET_ID],
        )
        self.assertIsNotNone(dispatch_request.sync_from_ts)
