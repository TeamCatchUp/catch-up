from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
from unittest.mock import patch

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
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncRequestedTarget
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.common.schemas import FullSyncTarget
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncDispatchStatus
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.dispatch.types import DispatchRequest
from catchup.sync.full.registry import get_full_sync_target_resolver
from catchup.sync.full.registry import list_registered_sync_connectors
from catchup.sync.full.resolvers.channel_talk_full_sync_resolver import (
    ChannelTalkFullSyncTargetResolver,
)
from catchup.sync.full.service import FullSyncService

CHANNEL_ID = "channel-123"
SPACE_ID = "space-123"
_RESOLVER_MODULE = "catchup.sync.full.resolvers.channel_talk_full_sync_resolver"
_LOAD_CONNECTION = f"{_RESOLVER_MODULE}.load_channel_talk_connection"
_LIST_DOCUMENT_CONNECTIONS = f"{_RESOLVER_MODULE}.list_channel_talk_document_connections"
_RUN_IN_THREADPOOL = f"{_RESOLVER_MODULE}.run_in_threadpool"
_FULL_SYNC_SERVICE_MODULE = "catchup.sync.full.service"


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
    space_id: str = SPACE_ID,
    space_name: str = "Help Center",
    association_status: ChannelTalkDocumentAssociationStatus = (
        ChannelTalkDocumentAssociationStatus.API_VERIFIED
    ),
) -> ChannelTalkDocumentCredentialsRecord:
    return ChannelTalkDocumentCredentialsRecord(
        channel_id=channel_id,
        space_id=space_id,
        space_name=space_name,
        access_key="documents-access-key",
        access_secret="documents-access-secret",
        association_status=association_status,
    )


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def _target(
    target_type: SyncTargetType,
    target_id: str,
) -> FullSyncRequestedTarget:
    return FullSyncRequestedTarget(target_type=target_type, target_id=target_id)


def _channel_target(target_id: str = CHANNEL_ID) -> FullSyncRequestedTarget:
    return _target(SyncTargetType.CHANNEL, target_id)


def _space_target(target_id: str = SPACE_ID) -> FullSyncRequestedTarget:
    return _target(SyncTargetType.SPACE, target_id)


class _FakeResolver:
    async def resolve_full_sync_targets(self, *, request):
        return FullSyncResolvedTargets(
            targets=[
                FullSyncTarget(
                    target_type=SyncTargetType.CHANNEL,
                    target_id=CHANNEL_ID,
                    target_name="Support",
                    metadata={
                        "target_kind": "channel_talk.channel",
                        "channel_id": CHANNEL_ID,
                    },
                )
            ]
        )


class _FakeDispatchService:
    def __init__(self) -> None:
        self.request: DispatchRequest | None = None

    async def dispatch(self, request: DispatchRequest) -> SyncDispatchResult:
        self.request = request
        return SyncDispatchResult(
            status=SyncDispatchStatus.ACCEPTED,
            connector=request.connector,
            scope_id=request.scope_id,
            job_id="job-123",
            event_ids=["event-123"],
            total_targets=len(request.event_seeds),
            queued_targets=len(request.event_seeds),
        )


class ChannelTalkFullSyncResolverTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.resolver = ChannelTalkFullSyncTargetResolver()
        self.run_in_threadpool_patcher = patch(
            _RUN_IN_THREADPOOL,
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_resolver_rejects_legacy_user_chat_alias(self) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[],
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "requested targets contain unknown channel_talk targets",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_channel_target("user_chat")],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_blank_scope_id(self) -> None:
        with self.assertRaisesRegex(SyncRequestException, "scope_id is required"):
            await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id="",
                    targets=[_channel_target()],
                    sync_from_ts="1713744000.000000",
                ),
            )

    async def test_resolver_skips_document_connection_lookup_for_channel_only_request(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                side_effect=AssertionError("document lookup should not run"),
            ),
        ):
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    targets=[_channel_target()],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(len(result.targets), 1)
        self.assertEqual(result.targets[0].target_id, CHANNEL_ID)

    async def test_resolver_rejects_unknown_channel_target_id(self) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[],
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "requested targets contain unknown channel_talk targets",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_channel_target("group")],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_invalid_channel_talk_target_type(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "requested targets contain invalid channel_talk target_type",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_target(SyncTargetType.REPOSITORY, CHANNEL_ID)],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_space_id_requested_as_channel_target(self) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                side_effect=AssertionError("document lookup should not run"),
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "requested targets contain unknown channel_talk targets",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_channel_target(SPACE_ID)],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_channel_id_requested_as_space_target(self) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[_build_document_connection_record()],
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "requested targets contain unknown channel_talk targets",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_space_target(CHANNEL_ID)],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_legacy_document_article_alias(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[_build_document_connection_record()],
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "requested targets contain unknown channel_talk targets",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_space_target("document_article")],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_selected_space_when_documents_not_connected(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[],
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "channel_talk documents is not connected for the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_space_target()],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_returns_selected_document_space_when_documents_connected(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[_build_document_connection_record()],
            ),
        ):
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    targets=[_space_target()],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(len(result.targets), 1)
        self.assertEqual(
            result.targets[0].target_id,
            SPACE_ID,
        )
        self.assertEqual(result.targets[0].target_name, "Help Center")
        self.assertEqual(result.targets[0].target_type.value, "space")
        self.assertEqual(
            result.targets[0].metadata,
            {
                "target_kind": "channel_talk.document_space",
                "channel_id": CHANNEL_ID,
                "space_id": SPACE_ID,
                "space_name": "Help Center",
            },
        )

    async def test_resolver_accepts_selected_document_space_id(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[_build_document_connection_record()],
            ),
        ):
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    targets=[_space_target()],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(len(result.targets), 1)
        self.assertEqual(result.targets[0].target_id, SPACE_ID)
        self.assertEqual(result.targets[0].target_type.value, "space")
        self.assertEqual(
            result.targets[0].metadata["target_kind"],
            "channel_talk.document_space",
        )

    async def test_resolver_accepts_second_document_space_for_same_channel(self) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[
                    _build_document_connection_record(
                        space_id="space-123",
                        space_name="Help Center",
                    ),
                    _build_document_connection_record(
                        space_id="space-456",
                        space_name="Developer Docs",
                    ),
                ],
            ),
        ):
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    targets=[_space_target("space-456")],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(len(result.targets), 1)
        self.assertEqual(result.targets[0].target_id, "space-456")
        self.assertEqual(result.targets[0].target_name, "Developer Docs")

    async def test_resolver_rejects_document_article_when_documents_channel_mismatches(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[_build_document_connection_record(
                    channel_id="channel-other"
                )],
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "channel_talk documents credentials are not API verified for the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_space_target()],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_document_article_when_documents_unverified(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[_build_document_connection_record(
                    association_status=ChannelTalkDocumentAssociationStatus.FAILED,
                )],
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "channel_talk documents credentials are not API verified for the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_space_target()],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_returns_mixed_channel_and_document_space_request(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[_build_document_connection_record()],
            ),
        ):
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    targets=[_channel_target(), _space_target()],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(
            [target.target_id for target in result.targets],
            [
                CHANNEL_ID,
                SPACE_ID,
            ],
        )

    async def test_resolver_rejects_blank_scope_before_connection_lookup(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            side_effect=AssertionError("connection lookup should not run"),
        ):
            with self.assertRaisesRegex(SyncRequestException, "scope_id is required"):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id="",
                        targets=[_channel_target()],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_missing_channel_talk_connection(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=None,
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "channel_talk is not connected for the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_channel_target()],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_passes_scope_id_to_connection_lookup(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ) as load_connection:
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    targets=[_channel_target()],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(result.targets[0].target_id, CHANNEL_ID)
        load_connection.assert_called_once_with(CHANNEL_ID)

    async def test_resolver_rejects_requested_channel_mismatch(self) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(channel_id="channel-other"),
            ),
            patch(
                _LIST_DOCUMENT_CONNECTIONS,
                return_value=[],
            ),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "Stored Channel Talk credentials do not match the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        targets=[_channel_target()],
                        sync_from_ts="1713744000.000000",
                    ),
                )


class FullSyncRegistryAdmissionTests(TestCase):
    def test_registry_includes_channel_talk_without_dropping_existing_connectors(
        self,
    ) -> None:
        registered = set(list_registered_sync_connectors())

        self.assertEqual(
            registered,
            {
                SyncConnector.SLACK,
                SyncConnector.GITHUB,
                SyncConnector.JIRA,
                SyncConnector.CONFLUENCE,
                SyncConnector.CHANNEL_TALK,
            },
        )
        self.assertIsNotNone(
            get_full_sync_target_resolver(SyncConnector.CHANNEL_TALK),
        )


class ChannelTalkFullSyncServiceDispatchTests(IsolatedAsyncioTestCase):
    async def test_dispatch_rejects_blank_scope_id_instead_of_deriving_from_metadata(
        self,
    ) -> None:
        dispatch_service = _FakeDispatchService()
        service = FullSyncService(dispatch_service=dispatch_service)

        with patch(
            f"{_FULL_SYNC_SERVICE_MODULE}.get_full_sync_target_resolver",
            return_value=_FakeResolver(),
        ):
            with self.assertRaisesRegex(SyncRequestException, "scope_id is required"):
                await service.dispatch(
                    connector=SyncConnector.CHANNEL_TALK,
                    request=FullSyncDispatchRequest(
                        scope_id="",
                        targets=[_channel_target()],
                        sync_from_ts="1713744000.000000",
                    ),
                )

        self.assertIsNone(dispatch_service.request)
