from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import Session
from sqlalchemy.orm import mapped_column

import catchup.db.channel_talk.repository as repository_module
from catchup.connectors.channel_talk.schemas import ChannelTalkChannel
from catchup.connectors.channel_talk.schemas import ChannelTalkChannelMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkCurrentChannel
from catchup.connectors.channel_talk.schemas import ChannelTalkGroupManagerMembership
from catchup.connectors.channel_talk.schemas import ChannelTalkGroupMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkManagerMetadata


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
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
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


class ChannelTalkRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        _Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.model_patchers = [
            patch.object(repository_module, "ChannelTalkCredentials", _ChannelTalkCredentials),
            patch.object(repository_module, "ChannelTalkChannelRow", _ChannelTalkChannel),
            patch.object(repository_module, "ChannelTalkManagerRow", _ChannelTalkManager),
            patch.object(repository_module, "ChannelTalkGroupRow", _ChannelTalkGroup),
            patch.object(repository_module, "ChannelTalkGroupManagerRow", _ChannelTalkGroupManager),
        ]
        for patcher in self.model_patchers:
            patcher.start()
        self.addCleanup(self._stop_patchers)
        self.credentials_repo = repository_module.ChannelTalkCredentialsRepository(self.db)
        self.metadata_repo = repository_module.ChannelTalkMetadataRepository(self.db)

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
                ),
                ChannelTalkManagerMetadata(
                    channel_id="channel-123",
                    manager_id="manager-2",
                    name="Park",
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
        groups = self.metadata_repo.list_groups_by_channel("channel-123")
        memberships = self.metadata_repo.list_group_manager_memberships(channel_id="channel-123")

        self.assertIsNotNone(channel)
        self.assertEqual(channel.channel_name, "Support")
        self.assertCountEqual([item.manager_id for item in managers], ["manager-1", "manager-2"])
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
        self.assertEqual(self.credentials_repo.get_connection().channel_name, "Support")
