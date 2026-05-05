from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from catchup.auth.dependencies import require_admin_user
from catchup.db.dependencies import get_db
from catchup.db.models import Base
from catchup.db.models import ChannelTalkManager
from catchup.db.models import ConfluenceUser
from catchup.db.models import GitHubUser
from catchup.db.models import JiraUser
from catchup.db.models import OAuthUser
from catchup.db.models import PreMappingBuffer
from catchup.db.models import SlackUser
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.db.models import UserSourceMapping
from catchup.db.models import UserStatus
from catchup.mapping.resolver import sync_users_to_pre_mapping_buffer
from catchup.server.admin.api import router


def _sqlite_upsert_user_source_mapping(
    db: Session,
    user_id: int,
    source_type: SourceType,
    external_user_identifier: str,
) -> None:
    mapping = db.scalar(
        select(UserSourceMapping).where(
            UserSourceMapping.user_id == user_id,
            UserSourceMapping.source_type == source_type,
        )
    )
    if mapping:
        mapping.external_user_identifier = external_user_identifier
        return

    db.add(
        UserSourceMapping(
            user_id=user_id,
            source_type=source_type,
            external_user_identifier=external_user_identifier,
        )
    )


class ChannelTalkUserSyncMappingApiTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                OAuthUser.__table__,
                PreMappingBuffer.__table__,
                UserSourceMapping.__table__,
                JiraUser.__table__,
                SlackUser.__table__,
                GitHubUser.__table__,
                ConfluenceUser.__table__,
                ChannelTalkManager.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = self._get_db
        self.app.dependency_overrides[require_admin_user] = lambda: object()
        self.client = TestClient(self.app)

        self.resolver_upsert_patcher = patch(
            "catchup.mapping.resolver.upsert_user_source_mapping",
            side_effect=_sqlite_upsert_user_source_mapping,
        )
        self.admin_upsert_patcher = patch(
            "catchup.server.admin.api.upsert_user_source_mapping",
            side_effect=_sqlite_upsert_user_source_mapping,
        )
        self.resolver_upsert_patcher.start()
        self.admin_upsert_patcher.start()

    def tearDown(self) -> None:
        self.admin_upsert_patcher.stop()
        self.resolver_upsert_patcher.stop()
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def _get_db(self):
        yield self.db

    def _add_registered_oauth_user(
        self,
        *,
        email: str = "agent@example.com",
        sub: str = "sub-agent",
        name: str = "Agent Kim",
    ) -> User:
        user = User(
            email=email,
            name=name,
            provider="keycloak",
            status=UserStatus.ACTIVE,
        )
        self.db.add(user)
        self.db.flush()
        self.db.add(
            OAuthUser(
                sub=sub,
                name=name,
                email=email,
                status="ACTIVE",
                user_id=user.id,
            )
        )
        self.db.flush()
        return user

    def _add_channel_talk_manager(
        self,
        *,
        manager_id: str = "manager-1",
        email: str | None = "agent@example.com",
        name: str | None = "Agent Kim",
        removed: bool | None = False,
    ) -> ChannelTalkManager:
        manager = ChannelTalkManager(
            channel_id="channel-1",
            manager_id=manager_id,
            name=name,
            email=email,
            removed=removed,
            avatar_url=f"https://example.com/{manager_id}.png",
        )
        self.db.add(manager)
        self.db.flush()
        return manager

    def test_channel_talk_sync_creates_registered_pre_mapping_and_source_mapping(self) -> None:
        user = self._add_registered_oauth_user()
        self._add_channel_talk_manager()
        self._add_channel_talk_manager(
            manager_id="removed-manager",
            email="removed@example.com",
            removed=True,
        )

        result = sync_users_to_pre_mapping_buffer(self.db, SourceType.CHANNEL_TALK)
        self.db.commit()

        pre_mapping = self.db.scalar(
            select(PreMappingBuffer).where(
                PreMappingBuffer.source_type == SourceType.CHANNEL_TALK,
                PreMappingBuffer.email == "agent@example.com",
            )
        )
        source_mapping = self.db.scalar(
            select(UserSourceMapping).where(
                UserSourceMapping.user_id == user.id,
                UserSourceMapping.source_type == SourceType.CHANNEL_TALK,
            )
        )

        self.assertEqual(result["success"], 1)
        self.assertEqual(result["mapping_created"], 1)
        self.assertIsNotNone(pre_mapping)
        self.assertEqual(pre_mapping.external_user_identifier, "manager-1")
        self.assertTrue(pre_mapping.is_registered)
        self.assertIsNotNone(source_mapping)
        self.assertEqual(source_mapping.external_user_identifier, "manager-1")

    def test_sync_status_endpoint_is_removed(self) -> None:
        self._add_registered_oauth_user()
        self._add_channel_talk_manager()
        sync_users_to_pre_mapping_buffer(self.db, SourceType.CHANNEL_TALK)
        self.db.commit()

        response = self.client.get(
            "/api/v1/admin/users/sync-status",
            params={"filter_type": "all", "page": 1, "size": 50},
        )

        self.assertEqual(response.status_code, 404)

    def test_channel_talk_vendor_users_excludes_removed_managers(self) -> None:
        self._add_channel_talk_manager(manager_id="active-manager")
        self._add_channel_talk_manager(
            manager_id="unknown-removed-manager",
            email="unknown@example.com",
            removed=None,
        )
        self._add_channel_talk_manager(
            manager_id="removed-manager",
            email="removed@example.com",
            removed=True,
        )
        self.db.commit()

        response = self.client.get(
            "/api/v1/admin/channel_talk/users",
            params={"page": 1, "size": 50},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(
            {item["id"] for item in payload["items"]},
            {"active-manager", "unknown-removed-manager"},
        )

    def test_channel_talk_bulk_update_upserts_and_deletes_registered_source_mapping(self) -> None:
        user = self._add_registered_oauth_user()
        self.db.commit()

        response = self.client.patch(
            "/api/v1/admin/channel_talk/pre-mappings/bulk",
            json={
                "items": [
                    {
                        "sub": "sub-agent",
                        "email": "agent@example.com",
                        "name": "Agent Kim",
                        "is_ignored": False,
                        "external_user_identifier": "manager-1",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        pre_mapping = self.db.scalar(
            select(PreMappingBuffer).where(
                PreMappingBuffer.sub == "sub-agent",
                PreMappingBuffer.source_type == SourceType.CHANNEL_TALK,
            )
        )
        source_mapping = self.db.scalar(
            select(UserSourceMapping).where(
                UserSourceMapping.user_id == user.id,
                UserSourceMapping.source_type == SourceType.CHANNEL_TALK,
            )
        )
        self.assertIsNotNone(pre_mapping)
        self.assertEqual(pre_mapping.external_user_identifier, "manager-1")
        self.assertTrue(pre_mapping.is_registered)
        self.assertIsNotNone(source_mapping)
        self.assertEqual(source_mapping.external_user_identifier, "manager-1")

        response = self.client.patch(
            "/api/v1/admin/channel_talk/pre-mappings/bulk",
            json={
                "items": [
                    {
                        "sub": "sub-agent",
                        "email": "agent@example.com",
                        "name": "Agent Kim",
                        "is_ignored": True,
                        "external_user_identifier": None,
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            self.db.scalar(
                select(PreMappingBuffer).where(
                    PreMappingBuffer.sub == "sub-agent",
                    PreMappingBuffer.source_type == SourceType.CHANNEL_TALK,
                )
            )
        )
        self.assertIsNone(
            self.db.scalar(
                select(UserSourceMapping).where(
                    UserSourceMapping.user_id == user.id,
                    UserSourceMapping.source_type == SourceType.CHANNEL_TALK,
                )
            )
        )
