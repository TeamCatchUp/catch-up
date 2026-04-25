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
from catchup.connectors.channel_talk.documents_client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.documents_schemas import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.documents_schemas import (
    ChannelTalkDocumentConnectRequest,
)
from catchup.connectors.channel_talk.documents_schemas import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.connectors.channel_talk.documents_schemas import ChannelTalkDocumentSpace
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPayloadError
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord


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
            client = ChannelTalkDocumentsApiClient(http_client=http_client)
            space = await client.get_current_space("documents-key", "documents-secret")

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
            client = ChannelTalkDocumentsApiClient(http_client=http_client)
            with self.assertRaises(ChannelTalkPayloadError):
                await client.get_current_space("documents-key", "documents-secret")


class _DocumentInstallStore:
    def __init__(self, *, base_channel_id: str | None = "channel-123") -> None:
        self.base_channel_id = base_channel_id
        self.stored_payload = None
        self.committed = False

    def get_base_connection(self):
        if self.base_channel_id is None:
            return None
        return ChannelTalkCredentialsRecord(
            channel_id=self.base_channel_id,
            channel_name="Support",
        )

    def get_document_connection(self, channel_id=None):
        return None

    def upsert_document_connection(self, payload):
        self.stored_payload = payload
        return payload.to_record()

    def delete_document_connection(self):
        return False

    def commit(self):
        self.committed = True


class _SpaceClient:
    def __init__(self, space: ChannelTalkDocumentSpace) -> None:
        self.space = space

    async def get_current_space(self, access_key: str, access_secret: str):
        return self.space


class ChannelTalkDocumentsInstallAdapterTests(IsolatedAsyncioTestCase):
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


class _MetadataStore:
    def __init__(self) -> None:
        self.authors = []
        self.nav_nodes = []
        self.commits = 0

    def get_document_connection(self, channel_id=None):
        return ChannelTalkDocumentCredentialsRecord(
            channel_id=channel_id,
            space_id="space-123",
            space_name="Help Center",
            access_key="documents-key",
            access_secret="documents-secret",
            association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
        )

    def upsert_document_space(self, payload, *, channel_id):
        return payload

    def bulk_upsert_document_authors(self, payloads):
        self.authors.extend(payloads)
        return payloads

    def bulk_upsert_document_nav_nodes(self, payloads):
        self.nav_nodes.extend(payloads)
        return payloads

    def commit(self):
        self.commits += 1


class _MetadataClient:
    async def get_current_space(self, access_key: str, access_secret: str):
        return ChannelTalkDocumentSpace(
            space_id="space-123",
            space_name="Help Center",
            channel_id="channel-123",
        )

    async def list_authors(self, access_key: str, access_secret: str, *, since=None):
        from catchup.connectors.channel_talk.documents_schemas import (
            ChannelTalkDocumentAuthorMetadata,
        )
        from catchup.connectors.channel_talk.documents_schemas import (
            ChannelTalkDocumentAuthorPage,
        )

        return ChannelTalkDocumentAuthorPage(
            authors=[ChannelTalkDocumentAuthorMetadata(author_id="author-1", name="Kim")]
        )

    async def list_nav_nodes(self, access_key: str, access_secret: str):
        from catchup.connectors.channel_talk.documents_schemas import (
            ChannelTalkDocumentNavNodeMetadata,
        )
        from catchup.connectors.channel_talk.documents_schemas import (
            ChannelTalkDocumentNavNodePage,
        )

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
