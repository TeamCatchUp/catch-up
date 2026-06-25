from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import Session
from sqlalchemy.orm import mapped_column

import catchup.db.channel_talk.repository as repository_module
from catchup.connectors.channel_talk.schemas.channel_metadata import ChannelTalkChannel
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkChannelMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupManagerMembership,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsUpsert,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorMetadata,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentNavNodeMetadata,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentSpace,
)


class _Base(DeclarativeBase):
    pass


class _ChannelTalkCredentials(_Base):
    __tablename__ = "channel_talk_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_key: Mapped[str] = mapped_column(String(512), nullable=False)
    access_secret: Mapped[str] = mapped_column(String(512), nullable=False)
    webhook_token: Mapped[str] = mapped_column(String(1024), nullable=False)
    credential_last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            name="uq_channel_talk_credentials_channel_id",
        ),
    )


class _ChannelTalkDocumentCredentials(_Base):
    __tablename__ = "channel_talk_document_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    space_id: Mapped[str] = mapped_column(String(128), nullable=False)
    space_name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_key: Mapped[str] = mapped_column(String(512), nullable=False)
    access_secret: Mapped[str] = mapped_column(String(512), nullable=False)
    credential_last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    association_status: Mapped[str] = mapped_column(String(32), nullable=False)
    polling_cycle_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_incremental_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_incremental_poll_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_incremental_poll_error: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )


class _ChannelTalkChannel(_Base):
    __tablename__ = "channel_talk_channels"

    channel_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    bot_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    homepage_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subdomain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class _ChannelTalkManager(_Base):
    __tablename__ = "channel_talk_managers"

    channel_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    manager_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mobile_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 실제 모델 rename과 같은 이름을 써서 repository round-trip을 같은 계약으로 검증한다.
    role_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    removed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    display_as_channel: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remote_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class _ChannelTalkGroup(_Base):
    __tablename__ = "channel_talk_groups"

    channel_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    remote_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remote_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class _ChannelTalkGroupManager(_Base):
    __tablename__ = "channel_talk_group_managers"

    channel_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    manager_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class _ChannelTalkDocumentAuthor(_Base):
    __tablename__ = "channel_talk_document_authors"

    channel_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    author_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class _ChannelTalkDocumentNavNode(_Base):
    __tablename__ = "channel_talk_document_nav_nodes"

    channel_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    nav_node_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    node_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelTalkRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        _Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.model_patchers = [
            patch.object(repository_module.db_models, "ChannelTalkCredentials", _ChannelTalkCredentials),
            patch.object(repository_module.db_models, "ChannelTalkChannel", _ChannelTalkChannel),
            patch.object(repository_module.db_models, "ChannelTalkManager", _ChannelTalkManager),
            patch.object(repository_module.db_models, "ChannelTalkGroup", _ChannelTalkGroup),
            patch.object(repository_module.db_models, "ChannelTalkGroupManager", _ChannelTalkGroupManager),
            patch.object(repository_module.db_models, "ChannelTalkDocumentCredentials", _ChannelTalkDocumentCredentials),
            patch.object(repository_module.db_models, "ChannelTalkDocumentAuthor", _ChannelTalkDocumentAuthor),
            patch.object(repository_module.db_models, "ChannelTalkDocumentNavNode", _ChannelTalkDocumentNavNode),
        ]
        for patcher in self.model_patchers:
            patcher.start()
        self.addCleanup(self._stop_patchers)
        self.credentials_repo = repository_module.ChannelTalkCredentialsRepository(self.db)
        self.metadata_repo = repository_module.ChannelTalkMetadataRepository(self.db)
        self.document_credentials_repo = repository_module.ChannelTalkDocumentCredentialsRepository(self.db)
        self.document_metadata_repo = repository_module.ChannelTalkDocumentMetadataRepository(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _stop_patchers(self) -> None:
        for patcher in reversed(self.model_patchers):
            patcher.stop()

    def test_metadata_rows_are_upserted_and_relation_rows_are_replaced(self) -> None:
        self.metadata_repo.upsert_channel_metadata(
            ChannelTalkChannelMetadata(
                channel_id="channel-123",
                channel_name="Support",
                subdomain="support",
            )
        )
        self.metadata_repo.bulk_upsert_managers(
            [
                ChannelTalkManagerMetadata(
                    channel_id="channel-123",
                    manager_id="manager-1",
                    name="Kim",
                    email="kim@example.com",
                    role_id="role-1",
                ),
                ChannelTalkManagerMetadata(
                    channel_id="channel-123",
                    manager_id="manager-2",
                    name="Park",
                    role_id="role-2",
                ),
            ]
        )
        self.metadata_repo.bulk_upsert_groups(
            [
                ChannelTalkGroupMetadata(
                    channel_id="channel-123",
                    group_id="group-1",
                    group_name="VIP",
                ),
            ]
        )
        self.metadata_repo.replace_group_managers(
            channel_id="channel-123",
            memberships=(
                ChannelTalkGroupManagerMembership(
                    channel_id="channel-123",
                    group_id="group-1",
                    manager_id="manager-1",
                ),
                ChannelTalkGroupManagerMembership(
                    channel_id="channel-123",
                    group_id="group-1",
                    manager_id="manager-2",
                ),
            ),
        )
        self.metadata_repo.replace_group_managers(
            channel_id="channel-123",
            memberships=(
                ChannelTalkGroupManagerMembership(
                    channel_id="channel-123",
                    group_id="group-1",
                    manager_id="manager-2",
                ),
            ),
        )

        channel = self.metadata_repo.get_channel_metadata("channel-123")
        managers = self.metadata_repo.list_managers_by_channel("channel-123")
        selected_managers = self.metadata_repo.list_managers_by_channel_and_ids(
            "channel-123",
            {"manager-2", "manager-missing"},
        )
        groups = self.metadata_repo.list_groups_by_channel("channel-123")
        memberships = self.metadata_repo.list_group_manager_memberships(channel_id="channel-123")

        # bulk upsert 리팩터링 뒤에도 manager role_id가 손실되지 않는지 함께 확인한다.
        self.assertIsNotNone(channel)
        self.assertEqual(channel.channel_name, "Support")
        self.assertCountEqual([item.manager_id for item in managers], ["manager-1", "manager-2"])
        self.assertCountEqual([item.role_id for item in managers], ["role-1", "role-2"])
        self.assertEqual([item.manager_id for item in selected_managers], ["manager-2"])
        self.assertEqual([item.group_id for item in groups], ["group-1"])
        self.assertEqual(
            [(item.group_id, item.manager_id) for item in memberships],
            [("group-1", "manager-2")],
        )

    def test_credentials_repository_only_handles_install_auth_rows(self) -> None:
        verified_at = datetime(2026, 4, 20, tzinfo=timezone.utc)

        record = self.credentials_repo.upsert_connection(
            repository_module.ChannelTalkCredentialsUpsert(
                access_key="access-key",
                access_secret="access-secret",
                webhook_token="webhook-token",
                current_channel=ChannelTalkCurrentChannel(
                    channel=ChannelTalkChannel(
                        id="channel-123",
                        name="Support",
                    )
                ),
                credential_last_verified_at=verified_at,
            )
        )

        self.assertEqual(record.channel_id, "channel-123")
        self.assertIsNotNone(record.id)
        self.assertEqual(
            self.credentials_repo.get_connection_by_id(record.id).channel_id,
            "channel-123",
        )
        self.assertEqual(self.credentials_repo.get_connection().channel_name, "Support")
        self.assertEqual(
            [item.channel_id for item in self.credentials_repo.list_connections()],
            ["channel-123"],
        )
        self.assertTrue(self.credentials_repo.delete_connection("channel-123"))
        self.assertIsNone(self.credentials_repo.get_connection("channel-123"))

    def test_document_credentials_are_upserted_loaded_and_deleted(self) -> None:
        verified_at = datetime(2026, 4, 25, tzinfo=timezone.utc)

        record = self.document_credentials_repo.upsert_document_connection(
            ChannelTalkDocumentCredentialsUpsert(
                channel_id="channel-123",
                access_key="documents-key",
                access_secret="documents-secret",
                space=ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="channel-123",
                ),
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
            )
        )

        self.assertEqual(record.channel_id, "channel-123")
        self.assertEqual(record.space_id, "space-123")
        self.assertEqual(record.access_secret, "documents-secret")
        status = ChannelTalkDocumentCredentialsStatus.from_record(record)
        self.assertNotIn("access_secret", status.model_dump())

        loaded = self.document_credentials_repo.get_document_connection("channel-123")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.association_status, ChannelTalkDocumentAssociationStatus.API_VERIFIED)
        self.assertEqual(
            [item.space_id for item in self.document_credentials_repo.list_document_connections()],
            ["space-123"],
        )
        self.assertTrue(
            self.document_credentials_repo.delete_document_connection_by_space_id(
                "space-123"
            )
        )
        self.assertIsNone(self.document_credentials_repo.get_document_connection("channel-123"))

    def test_document_credentials_round_trips_polling_cycle_hours(self) -> None:
        verified_at = datetime(2026, 4, 25, tzinfo=timezone.utc)

        record = self.document_credentials_repo.upsert_document_connection(
            ChannelTalkDocumentCredentialsUpsert(
                channel_id="channel-123",
                access_key="documents-key",
                access_secret="documents-secret",
                space=ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="channel-123",
                ),
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
                polling_cycle_hours=6,
            )
        )
        loaded = self.document_credentials_repo.get_document_connection(
            channel_id="channel-123",
            space_id="space-123",
        )

        self.assertEqual(record.polling_cycle_hours, 6)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.polling_cycle_hours, 6)
        self.assertEqual(
            ChannelTalkDocumentCredentialsStatus.from_record(loaded).polling_cycle_hours,
            6,
        )

    def test_document_credentials_due_polling_handles_naive_db_timestamps(self) -> None:
        verified_at = datetime(2026, 4, 25, 6, 0)
        now = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)

        self.document_credentials_repo.upsert_document_connection(
            ChannelTalkDocumentCredentialsUpsert(
                channel_id="channel-123",
                access_key="documents-key",
                access_secret="documents-secret",
                space=ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="channel-123",
                ),
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
                polling_cycle_hours=6,
            )
        )

        due = self.document_credentials_repo.list_due_document_connections(
            now=now,
            stale_started_before=now - timedelta(hours=1),
        )

        self.assertEqual([item.space_id for item in due], ["space-123"])

    def test_document_credentials_allows_multiple_spaces_for_one_channel(self) -> None:
        verified_at = datetime(2026, 4, 25, tzinfo=timezone.utc)

        self.document_credentials_repo.upsert_document_connection(
            ChannelTalkDocumentCredentialsUpsert(
                channel_id="channel-123",
                access_key="documents-key-1",
                access_secret="documents-secret-1",
                space=ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="channel-123",
                ),
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
            )
        )
        self.document_credentials_repo.upsert_document_connection(
            ChannelTalkDocumentCredentialsUpsert(
                channel_id="channel-123",
                access_key="documents-key-2",
                access_secret="documents-secret-2",
                space=ChannelTalkDocumentSpace(
                    space_id="space-456",
                    space_name="Developer Docs",
                    channel_id="channel-123",
                ),
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
            )
        )

        records = self.document_credentials_repo.list_document_connections(
            channel_id="channel-123"
        )
        loaded_second = self.document_credentials_repo.get_document_connection(
            channel_id="channel-123",
            space_id="space-456",
        )

        self.assertEqual(
            [record.space_id for record in records],
            ["space-123", "space-456"],
        )
        self.assertIsNotNone(loaded_second)
        self.assertEqual(loaded_second.space_name, "Developer Docs")

    def test_document_credentials_delete_is_scoped_to_channel(self) -> None:
        verified_at = datetime(2026, 4, 25, tzinfo=timezone.utc)
        self.document_credentials_repo.upsert_document_connection(
            ChannelTalkDocumentCredentialsUpsert(
                channel_id="channel-123",
                access_key="documents-key-1",
                access_secret="documents-secret-1",
                space=ChannelTalkDocumentSpace(
                    space_id="space-123",
                    space_name="Help Center",
                    channel_id="channel-123",
                ),
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
            )
        )
        self.document_credentials_repo.upsert_document_connection(
            ChannelTalkDocumentCredentialsUpsert(
                channel_id="channel-456",
                access_key="documents-key-2",
                access_secret="documents-secret-2",
                space=ChannelTalkDocumentSpace(
                    space_id="space-456",
                    space_name="Other Help Center",
                    channel_id="channel-456",
                ),
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
            )
        )

        self.assertTrue(
            self.document_credentials_repo.delete_document_connection_by_space_id(
                "space-123"
            )
        )

        self.assertIsNone(self.document_credentials_repo.get_document_connection("channel-123"))
        remaining = self.document_credentials_repo.get_document_connection("channel-456")
        self.assertIsNotNone(remaining)
        self.assertEqual(remaining.channel_id, "channel-456")

    def test_document_metadata_rows_are_upserted(self) -> None:
        authors = self.document_metadata_repo.bulk_upsert_document_authors(
            [
                ChannelTalkDocumentAuthorMetadata(
                    channel_id="channel-123",
                    space_id="space-123",
                    author_id="author-1",
                    name="Kim",
                    email="kim@example.com",
                )
            ]
        )
        nav_nodes = self.document_metadata_repo.bulk_upsert_document_nav_nodes(
            [
                ChannelTalkDocumentNavNodeMetadata(
                    channel_id="channel-123",
                    space_id="space-123",
                    nav_node_id="node-1",
                    entity_type="articles",
                    entity_id="article-1",
                    name="Intro",
                    rank=1,
                )
            ]
        )

        self.assertEqual(authors[0].author_id, "author-1")
        self.assertEqual(authors[0].email, "kim@example.com")
        self.assertEqual(nav_nodes[0].nav_node_id, "node-1")
        self.assertEqual(nav_nodes[0].entity_id, "article-1")

        document_author = self.db.execute(select(_ChannelTalkDocumentAuthor)).scalar_one()
        document_nav_node = self.db.execute(select(_ChannelTalkDocumentNavNode)).scalar_one()
        self.assertIsNotNone(document_author.synced_at)
        self.assertIsNotNone(document_nav_node.synced_at)
