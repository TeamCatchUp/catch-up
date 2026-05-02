from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase

import httpx

from catchup.connector_core.adapters.channel_talk.documents_install_auth_adapter import (
    ChannelTalkDocumentInstallAuthAdapter,
)
from catchup.connector_core.adapters.channel_talk.documents_metadata_sync_adapter import (
    ChannelTalkDocumentMetadataSyncAdapter,
)
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connectors.channel_talk.document_space.client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPayloadError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentConnectRequest,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorMetadata,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorPage,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentNavNodeMetadata,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentNavNodePage,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentSpace,
)
from catchup.connectors.channel_talk.service import (
    ChannelTalkDocumentCredentialsService,
)


class ChannelTalkDocumentsClientTests(IsolatedAsyncioTestCase):
    async def test_get_current_space_uses_basic_auth_and_parses_payload(self) -> None:
        seen_authorization: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            seen_authorization.append(request.headers["Authorization"])
            self.assertEqual(str(request.url), "https://document-api.channel.io/open/v1/spaces/$me")
            return httpx.Response(
                200,
                json={
                    "space": {
                        "id": "space-123",
                        "name": "Help Center",
                        "channelId": "channel-123",
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            space = await client.get_current_space()

        self.assertEqual(space.space_id, "space-123")
        self.assertEqual(space.space_name, "Help Center")
        self.assertEqual(space.channel_id, "channel-123")
        self.assertEqual(seen_authorization, ["Basic ZG9jdW1lbnRzLWtleTpkb2N1bWVudHMtc2VjcmV0"])

    async def test_get_current_space_rejects_payload_without_channel_id(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "space": {
                        "id": "space-123",
                        "name": "Help Center",
                    }
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = ChannelTalkDocumentsApiClient(access_key="documents-key", access_secret="documents-secret", http_client=http_client)
            with self.assertRaises(ChannelTalkPayloadError):
                await client.get_current_space()


class _DocumentInstallStore:
    def __init__(self, *, base_channel_id: str | None = "channel-123") -> None:
        self.base_channel_id = base_channel_id
        self.stored_payload = None
        self.deleted_space_id = None
        self.delete_result = False
        self.committed = False

    def get_base_connection(self):
        if self.base_channel_id is None:
            return None
        return ChannelTalkCredentialsRecord(
            channel_id=self.base_channel_id,
            channel_name="Support",
        )

    def get_document_connection(self, channel_id=None, space_id=None):
        return None

    def list_document_connections(self, channel_id=None):
        return []

    def upsert_document_connection(self, payload):
        self.stored_payload = payload
        return payload.to_record()

    def delete_document_connection_by_space_id(self, space_id):
        self.deleted_space_id = space_id
        return self.delete_result

    def commit(self):
        self.committed = True


class _SpaceClient:
    def __init__(self, space: ChannelTalkDocumentSpace) -> None:
        self.space = space

    async def get_current_space(self):
        return self.space


class ChannelTalkDocumentsInstallAdapterTests(IsolatedAsyncioTestCase):
    async def test_service_validate_connection_does_not_persist(self) -> None:
        store = _DocumentInstallStore()
        service = ChannelTalkDocumentCredentialsService(
            store=store,
            client=_SpaceClient(
                ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="channel-123",
                )
            ),
        )

        status = await service.validate_connection(
            ChannelTalkDocumentConnectRequest(
                access_key="documents-key",
                access_secret="documents-secret",
            )
        )

        self.assertFalse(status.installed)
        self.assertEqual(status.channel_id, "channel-123")
        self.assertEqual(status.association_status, ChannelTalkDocumentAssociationStatus.API_VERIFIED)
        self.assertIsNone(store.stored_payload)
        self.assertFalse(store.committed)

    async def test_validate_connection_checks_relation_without_persisting(self) -> None:
        store = _DocumentInstallStore()
        adapter = ChannelTalkDocumentInstallAuthAdapter(
            store=store,
            client=_SpaceClient(
                ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="channel-123",
                )
            ),
        )

        status = await adapter.validate_connection(
            ChannelTalkDocumentConnectRequest(
                access_key="documents-key",
                access_secret="documents-secret",
            )
        )

        self.assertFalse(status.installed)
        self.assertEqual(status.channel_id, "channel-123")
        self.assertEqual(status.space_id, "space-123")
        self.assertEqual(status.space_name, "Help Center")
        self.assertEqual(status.association_status, ChannelTalkDocumentAssociationStatus.API_VERIFIED)
        self.assertIsNone(store.stored_payload)
        self.assertFalse(store.committed)

    async def test_api_relation_sets_api_verified(self) -> None:
        store = _DocumentInstallStore()
        adapter = ChannelTalkDocumentInstallAuthAdapter(
            store=store,
            client=_SpaceClient(
                ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="channel-123",
                )
            ),
        )

        status = await adapter.connect(
            request=ChannelTalkDocumentConnectRequest(
                access_key="documents-key",
                access_secret="documents-secret",
            ),
            validated_target=await adapter.validate_credentials(
                ChannelTalkDocumentConnectRequest(
                    access_key="documents-key",
                    access_secret="documents-secret",
                )
            ),
            verified_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
        )

        self.assertTrue(status.installed)
        self.assertEqual(status.association_status, ChannelTalkDocumentAssociationStatus.API_VERIFIED)
        self.assertTrue(store.committed)

    async def test_conflicting_relation_fails(self) -> None:
        adapter = ChannelTalkDocumentInstallAuthAdapter(
            store=_DocumentInstallStore(),
            client=_SpaceClient(
                ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="other-channel",
                )
            ),
        )

        with self.assertRaises(ChannelTalkConflictError):
            await adapter.connect(
                request=ChannelTalkDocumentConnectRequest(
                    access_key="documents-key",
                    access_secret="documents-secret",
                ),
                validated_target=await adapter.validate_credentials(
                    ChannelTalkDocumentConnectRequest(
                        access_key="documents-key",
                        access_secret="documents-secret",
                    )
                ),
                verified_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
            )

    async def test_uninstall_deletes_document_connection_by_space_id(self) -> None:
        store = _DocumentInstallStore(base_channel_id="channel-123")
        store.delete_result = True
        adapter = ChannelTalkDocumentInstallAuthAdapter(store=store)

        result = await adapter.uninstall("space-123")

        self.assertTrue(result.removed)
        self.assertEqual(store.deleted_space_id, "space-123")
        self.assertTrue(store.committed)

    async def test_uninstall_without_space_id_fails_without_deleting_documents(self) -> None:
        store = _DocumentInstallStore(base_channel_id=None)
        store.delete_result = True
        adapter = ChannelTalkDocumentInstallAuthAdapter(store=store)

        with self.assertRaisesRegex(ChannelTalkValidationError, "space_id is required"):
            await adapter.uninstall()
        self.assertIsNone(store.deleted_space_id)
        self.assertFalse(store.committed)


class _MetadataStore:
    def __init__(self) -> None:
        self.authors = []
        self.nav_nodes = []
        self.commits = 0

    def get_document_connection(self, channel_id=None, space_id=None):
        if space_id is not None and space_id != "space-123":
            return None
        return ChannelTalkDocumentCredentialsRecord(
            channel_id=channel_id,
            space_id="space-123",
            space_name="Help Center",
            access_key="documents-key",
            access_secret="documents-secret",
            association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
        )

    def list_document_connections(self, channel_id=None):
        return [self.get_document_connection("channel-123")]

    def bulk_upsert_document_authors(self, payloads):
        self.authors.extend(payloads)
        return payloads

    def bulk_upsert_document_nav_nodes(self, payloads):
        self.nav_nodes.extend(payloads)
        return payloads

    def commit(self):
        self.commits += 1


class _MetadataClient:
    async def get_current_space(self):
        return ChannelTalkDocumentSpace(
            space_id="space-123",
            space_name="Help Center",
            channel_id="channel-123",
        )

    async def list_authors(self, *, since=None):
        return ChannelTalkDocumentAuthorPage(
            authors=[ChannelTalkDocumentAuthorMetadata(author_id="author-1", name="Kim")]
        )

    async def list_nav_nodes(self):
        return ChannelTalkDocumentNavNodePage(
            nav_nodes=[
                ChannelTalkDocumentNavNodeMetadata(
                    nav_node_id="node-1",
                    entity_type="articles",
                    entity_id="article-1",
                )
            ]
        )


class ChannelTalkDocumentsMetadataAdapterTests(IsolatedAsyncioTestCase):
    async def test_metadata_sync_persists_authors_and_nav_nodes(self) -> None:
        store = _MetadataStore()
        adapter = ChannelTalkDocumentMetadataSyncAdapter(
            store=store,
            client=_MetadataClient(),
        )

        plan = await adapter.build_plan(
            MetadataSyncRequest(
                connector=ConnectorKey.CHANNEL_TALK,
                tenant_id="channel-123",
            )
        )
        completed = {}
        for step in plan.steps:
            completed[step.name] = await step.run(completed)

        self.assertEqual(completed["document_authors"].synced_count, 1)
        self.assertEqual(completed["document_nav_nodes"].synced_count, 1)
        self.assertEqual(store.authors[0].channel_id, "channel-123")
        self.assertEqual(store.nav_nodes[0].space_id, "space-123")
