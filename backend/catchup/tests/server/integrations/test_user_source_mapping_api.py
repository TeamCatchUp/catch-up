from __future__ import annotations

from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from catchup.auth.dependencies import require_admin_user
from catchup.db.models import Base
from catchup.db.models import ChannelTalkManager
from catchup.db.models import ConfluenceUser
from catchup.db.models import GitHubUser
from catchup.db.models import JiraUser
from catchup.db.models import JobLevel
from catchup.db.models import OAuthUser
from catchup.db.models import SlackUser
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.models import UserSourceMapping
from catchup.db.models import UserStatus
from catchup.mapping.user_source_mapping_service import UserSourceMappingApplication
from catchup.server.integrations import api as integrations_api


class UserSourceMappingApiTests(TestCase):
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
                UserSourceMapping.__table__,
                JiraUser.__table__,
                SlackUser.__table__,
                GitHubUser.__table__,
                ConfluenceUser.__table__,
                ChannelTalkManager.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.original_user_source_mapping_application = (
            integrations_api.user_source_mapping_application
        )
        integrations_api.user_source_mapping_application = UserSourceMappingApplication(
            db=self.db
        )
        self.app = FastAPI()
        self.app.include_router(integrations_api.router)
        self.app.dependency_overrides[require_admin_user] = lambda: object()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        integrations_api.user_source_mapping_application = (
            self.original_user_source_mapping_application
        )
        self.db.close()
        self.engine.dispose()

    def _add_user(
        self,
        *,
        email: str = "agent@example.com",
        name: str = "Agent Kim",
        sub: str = "sub-agent",
    ) -> User:
        user = User(
            email=email,
            name=name,
            role=UserRole.USER,
            provider="keycloak",
            department="engineering",
            job_level=JobLevel.MEMBER,
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
    ) -> None:
        self.db.add(
            ChannelTalkManager(
                channel_id="channel-1",
                manager_id=manager_id,
                name=name,
                email=email,
                removed=removed,
                avatar_url=f"https://example.com/{manager_id}.png",
            )
        )
        self.db.flush()

    def _add_github_mapping(self, user: User) -> None:
        self.db.add(
            GitHubUser(
                database_id=1,
                login="agent-github",
                name="Agent GitHub",
                email=user.email,
                avatar_url="https://example.com/github.png",
            )
        )
        self.db.add(
            UserSourceMapping(
                user_id=user.id,
                source_type=SourceType.GITHUB,
                external_user_identifier="agent-github",
            )
        )
        self.db.flush()

    def test_items_do_not_show_channel_talk_from_email_match_without_mapping(self) -> None:
        user = self._add_user()
        self._add_channel_talk_manager()
        self._add_github_mapping(user)
        self.db.commit()

        response = self.client.get(
            "/api/v1/integrations/user-source-mapping",
            params={"page": 1, "size": 50},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertIsNone(payload["items"][0]["channel_talk"])

    def test_refresh_inserts_missing_channel_talk_mapping_and_preserves_it(self) -> None:
        user = self._add_user()
        self._add_channel_talk_manager()
        self.db.commit()

        response = self.client.post(
            "/api/v1/integrations/user-source-mapping/refresh"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["scanned_users"], 1)
        self.assertEqual(payload["inserted"]["channel_talk"], 1)
        mapping = self.db.scalar(
            select(UserSourceMapping).where(
                UserSourceMapping.user_id == user.id,
                UserSourceMapping.source_type == SourceType.CHANNEL_TALK,
            )
        )
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.external_user_identifier, "manager-1")

        response = self.client.post(
            "/api/v1/integrations/user-source-mapping/refresh"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["inserted"]["channel_talk"], 0)
        self.assertEqual(payload["skipped_existing"]["channel_talk"], 1)

    def test_refresh_does_not_overwrite_existing_mapping(self) -> None:
        user = self._add_user()
        self._add_channel_talk_manager(manager_id="email-match-manager")
        self.db.add(
            UserSourceMapping(
                user_id=user.id,
                source_type=SourceType.CHANNEL_TALK,
                external_user_identifier="manual-manager",
            )
        )
        self.db.commit()

        response = self.client.post(
            "/api/v1/integrations/user-source-mapping/refresh"
        )

        self.assertEqual(response.status_code, 200)
        mapping = self.db.scalar(
            select(UserSourceMapping).where(
                UserSourceMapping.user_id == user.id,
                UserSourceMapping.source_type == SourceType.CHANNEL_TALK,
            )
        )
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.external_user_identifier, "manual-manager")

    def test_items_show_channel_talk_only_through_user_source_mapping(self) -> None:
        user = self._add_user()
        self._add_channel_talk_manager(
            manager_id="manager-1",
            email="different@example.com",
        )
        self.db.add(
            UserSourceMapping(
                user_id=user.id,
                source_type=SourceType.CHANNEL_TALK,
                external_user_identifier="manager-1",
            )
        )
        self.db.commit()

        response = self.client.get(
            "/api/v1/integrations/user-source-mapping",
            params={"page": 1, "size": 50},
        )

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["channel_talk"]["name"], "Agent Kim")
        self.assertEqual(item["channel_talk"]["identifier"], "different@example.com")

    def test_filter_returns_users_with_requested_source_mapping(self) -> None:
        channel_talk_user = self._add_user(
            email="channel@example.com",
            sub="sub-channel",
        )
        github_user = self._add_user(
            email="github@example.com",
            sub="sub-github",
        )
        self._add_channel_talk_manager(
            manager_id="manager-channel",
            email="channel@example.com",
        )
        self._add_github_mapping(github_user)
        self.db.add(
            UserSourceMapping(
                user_id=channel_talk_user.id,
                source_type=SourceType.CHANNEL_TALK,
                external_user_identifier="manager-channel",
            )
        )
        self.db.commit()

        response = self.client.get(
            "/api/v1/integrations/user-source-mapping",
            params={"page": 1, "size": 50},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)

        response = self.client.get(
            "/api/v1/integrations/user-source-mapping",
            params={"filter": "channel_talk", "page": 1, "size": 50},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "channel@example.com")
        self.assertIsNotNone(payload["items"][0]["channel_talk"])

    def test_mapping_status_counts_user_source_mappings(self) -> None:
        user = self._add_user()
        self._add_channel_talk_manager()
        self.db.add(
            UserSourceMapping(
                user_id=user.id,
                source_type=SourceType.CHANNEL_TALK,
                external_user_identifier="manager-1",
            )
        )
        self.db.commit()

        response = self.client.get("/api/v1/integrations/user-source-mapping/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["channel_talk"]["users"], 1)
        self.assertEqual(payload["channel_talk"]["mapped"], 1)
        self.assertNotIn("premap", payload["channel_talk"])
        self.assertEqual(payload["github"]["mapped"], 0)
