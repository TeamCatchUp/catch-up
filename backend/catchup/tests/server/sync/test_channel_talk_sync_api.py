from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
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


def _build_document_connection_record(
    *,
    channel_id: str = CHANNEL_ID,
) -> ChannelTalkDocumentCredentialsRecord:
    return ChannelTalkDocumentCredentialsRecord(
        channel_id=channel_id,
        space_id="space-123",
        space_name="Help Center",
        access_key="documents-access-key",
        access_secret="documents-access-secret",
        association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
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

    def test_get_targets_returns_registered_channel_with_scope_param(self) -> None:
        with (
            patch(
                "catchup.sync.query_service.load_channel_talk_connection",
                return_value=_build_connection_record(),
            ),
            patch(
                "catchup.sync.query_service.load_channel_talk_document_connection",
                return_value=_build_document_connection_record(),
            ),
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
                "total_targets": 2,
                "targets": [
                    {
                        "target_id": CHANNEL_ID,
                        "display_name": "Support",
                        "target_type": "channel",
                        "is_accessible": True,
                        "metadata": {
                            "target_kind": "channel_talk.channel",
                            "channel_id": CHANNEL_ID,
                        },
                    },
                    {
                        "target_id": "space-123",
                        "display_name": "Help Center",
                        "target_type": "space",
                        "is_accessible": True,
                        "metadata": {
                            "target_kind": "channel_talk.document_space",
                            "channel_id": CHANNEL_ID,
                            "space_id": "space-123",
                            "space_name": "Help Center",
                        },
                    },
                ],
            },
        )

    def test_get_targets_rejects_missing_scope_id_for_channel_talk(self) -> None:
        response = self.client.get(
            "/api/v1/sync/targets",
            params={
                "connector": "channel_talk",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertEqual(
            response.json()["detail"]["message"],
            "scope_id is required",
        )

    def test_get_targets_rejects_missing_scope_id_for_non_channel_talk(self) -> None:
        response = self.client.get(
            "/api/v1/sync/targets",
            params={
                "connector": "slack",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertEqual(
            response.json()["detail"]["message"],
            "scope_id is required",
        )

    def test_get_targets_rejects_missing_channel_talk_connection(self) -> None:
        with (
            patch(
                "catchup.sync.query_service.load_channel_talk_connection",
                return_value=None,
            ),
            patch(
                "catchup.sync.query_service.load_channel_talk_document_connection",
                return_value=_build_document_connection_record(),
            ),
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
            "channel_talk is not connected for the requested channel",
        )

    def test_get_targets_rejects_requested_channel_mismatch(self) -> None:
        with (
            patch(
                "catchup.sync.query_service.load_channel_talk_connection",
                return_value=_build_connection_record(channel_id="channel-other"),
            ),
            patch(
                "catchup.sync.query_service.load_channel_talk_document_connection",
                return_value=_build_document_connection_record(),
            ),
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

    def test_post_full_accepts_channel_talk_with_typed_targets(
        self,
    ) -> None:
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
                    "targets": [
                        {
                            "target_type": "channel",
                            "target_id": CHANNEL_ID,
                        }
                    ],
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
            [
                {
                    "target_type": target.target_type.value,
                    "target_id": target.target_id,
                }
                for target in dispatch_request.targets
            ],
            [
                {
                    "target_type": "channel",
                    "target_id": CHANNEL_ID,
                }
            ],
        )
        self.assertIsNotNone(dispatch_request.sync_from_ts)

    def test_post_full_rejects_legacy_target_ids_request_shape(self) -> None:
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
                    "target_ids": [CHANNEL_ID],
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(stub_service.calls, [])

    def test_post_full_rejects_target_ids_even_when_targets_are_present(self) -> None:
        response = self.client.post(
            "/api/v1/sync/full",
            json={
                "connector": "channel_talk",
                "scope_id": CHANNEL_ID,
                "targets": [
                    {
                        "target_type": "channel",
                        "target_id": CHANNEL_ID,
                    }
                ],
                "target_ids": [CHANNEL_ID],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_post_full_rejects_blank_target_id(self) -> None:
        response = self.client.post(
            "/api/v1/sync/full",
            json={
                "connector": "channel_talk",
                "scope_id": CHANNEL_ID,
                "targets": [
                    {
                        "target_type": "channel",
                        "target_id": " ",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_post_full_rejects_invalid_target_type(self) -> None:
        response = self.client.post(
            "/api/v1/sync/full",
            json={
                "connector": "channel_talk",
                "scope_id": CHANNEL_ID,
                "targets": [
                    {
                        "target_type": "group",
                        "target_id": CHANNEL_ID,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_post_full_rejects_empty_targets(self) -> None:
        response = self.client.post(
            "/api/v1/sync/full",
            json={
                "connector": "channel_talk",
                "scope_id": CHANNEL_ID,
                "targets": [],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_post_full_deduplicates_targets_by_type_and_id(self) -> None:
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
                    "targets": [
                        {
                            "target_type": "channel",
                            "target_id": CHANNEL_ID,
                        },
                        {
                            "target_type": "channel",
                            "target_id": CHANNEL_ID,
                        },
                    ],
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(stub_service.calls), 1)
        _, dispatch_request = stub_service.calls[0]
        self.assertEqual(len(dispatch_request.targets), 1)

    def test_targets_response_can_be_reused_as_full_sync_targets_request(
        self,
    ) -> None:
        stub_service = _StubFullSyncService()

        with (
            patch(
                "catchup.sync.query_service.load_channel_talk_connection",
                return_value=_build_connection_record(),
            ),
            patch(
                "catchup.sync.query_service.load_channel_talk_document_connection",
                return_value=_build_document_connection_record(),
            ),
        ):
            targets_response = self.client.get(
                "/api/v1/sync/targets",
                params={
                    "connector": "channel_talk",
                    "scope_id": CHANNEL_ID,
                },
            )

        target_payloads = [
            {
                "target_type": target["target_type"],
                "target_id": target["target_id"],
            }
            for target in targets_response.json()["targets"]
        ]

        with patch(
            "catchup.server.sync.api.get_full_sync_service",
            return_value=stub_service,
        ):
            response = self.client.post(
                "/api/v1/sync/full",
                json={
                    "connector": "channel_talk",
                    "scope_id": targets_response.json()["scope_id"],
                    "targets": target_payloads,
                },
            )

        self.assertEqual(response.status_code, 202)
        _, dispatch_request = stub_service.calls[0]
        self.assertEqual(dispatch_request.scope_id, CHANNEL_ID)
        self.assertEqual(len(dispatch_request.targets), 2)
        self.assertEqual(dispatch_request.targets[0].target_type.value, "channel")
        self.assertEqual(dispatch_request.targets[0].target_id, CHANNEL_ID)
        self.assertEqual(dispatch_request.targets[1].target_type.value, "space")
        self.assertEqual(dispatch_request.targets[1].target_id, "space-123")
