from __future__ import annotations

from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from catchup.auth.dependencies import require_admin_user
from catchup.db.models import Base
from catchup.db.models import ChannelTalkManager
from catchup.db.models import ConfluenceUser
from catchup.db.models import GitHubUser
from catchup.db.models import JiraAccountType
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
        login = f"github-{user.id}"
        self.db.add(
            GitHubUser(
                database_id=user.id,
                login=login,
                name="Agent GitHub",
                email=user.email,
                avatar_url="https://example.com/github.png",
            )
        )
        self._add_user_source_mapping(user, SourceType.GITHUB, login)
        self.db.flush()

    def _add_jira_mapping(self, user: User) -> None:
        account_id = f"jira-account-{user.id}"
        self.db.add(
            JiraUser(
                cloud_id="jira-cloud",
                account_id=account_id,
                account_type=JiraAccountType.ATLASSIAN,
                active=True,
                display_name=f"Jira {user.name}",
                email_address=user.email,
                avatar_url="https://example.com/jira.png",
            )
        )
        self._add_user_source_mapping(user, SourceType.JIRA, account_id)
        self.db.flush()

    def _add_confluence_mapping(self, user: User) -> None:
        account_id = f"confluence-account-{user.id}"
        self.db.add(
            ConfluenceUser(
                cloud_id="confluence-cloud",
                account_id=account_id,
                account_type="atlassian",
                display_name=f"Confluence {user.name}",
                public_name=user.name,
                email=user.email,
                avatar_url="https://example.com/confluence.png",
            )
        )
        self._add_user_source_mapping(user, SourceType.CONFLUENCE, account_id)
        self.db.flush()

    def _add_slack_mapping(self, user: User) -> None:
        slack_user_id = f"U{user.id}"
        self.db.add(
            SlackUser(
                team_id="T1",
                user_id=slack_user_id,
                name=f"slack-{user.id}",
                real_name=f"Slack {user.name}",
                deleted=False,
                email=user.email,
                display_name=user.name,
                avatar_url="https://example.com/slack.png",
                is_bot=False,
                is_admin=False,
                is_owner=False,
                is_restricted=False,
            )
        )
        self._add_user_source_mapping(user, SourceType.SLACK, slack_user_id)
        self.db.flush()

    def _add_channel_talk_mapping(self, user: User) -> None:
        manager_id = f"manager-{user.id}"
        self._add_channel_talk_manager(
            manager_id=manager_id,
            email=user.email,
            name=f"Channel {user.name}",
        )
        self._add_user_source_mapping(user, SourceType.CHANNEL_TALK, manager_id)

    def _add_user_source_mapping(
        self,
        user: User,
        source_type: SourceType,
        external_user_identifier: str,
    ) -> None:
        self.db.add(
            UserSourceMapping(
                user_id=user.id,
                source_type=source_type,
                external_user_identifier=external_user_identifier,
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

    def test_list_items_bulk_loads_source_info_for_page(self) -> None:
        first_user = self._add_user(email="first@example.com", sub="sub-first")
        second_user = self._add_user(email="second@example.com", sub="sub-second")
        self._add_channel_talk_manager(
            manager_id="manager-first",
            email="first-source@example.com",
            name="First Manager",
        )
        self._add_channel_talk_manager(
            manager_id="manager-second",
            email="second-source@example.com",
            name="Second Manager",
        )
        self.db.add_all(
            [
                UserSourceMapping(
                    user_id=first_user.id,
                    source_type=SourceType.CHANNEL_TALK,
                    external_user_identifier="manager-first",
                ),
                UserSourceMapping(
                    user_id=second_user.id,
                    source_type=SourceType.CHANNEL_TALK,
                    external_user_identifier="manager-second",
                ),
            ]
        )
        self.db.commit()

        statements: list[str] = []

        def track_statement(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", track_statement)
        try:
            response = self.client.get(
                "/api/v1/integrations/user-source-mapping",
                params={"page": 1, "size": 50},
            )
        finally:
            event.remove(self.engine, "before_cursor_execute", track_statement)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(
            {
                item["channel_talk"]["name"]
                for item in payload["items"]
                if item["channel_talk"] is not None
            },
            {"First Manager", "Second Manager"},
        )
        self.assertLessEqual(len(statements), 4)

    def test_mapping_status_full_treats_jira_or_confluence_as_atlassian(self) -> None:
        jira_user = self._add_user(email="jira-full@example.com", sub="sub-jira-full")
        confluence_user = self._add_user(
            email="confluence-full@example.com",
            sub="sub-confluence-full",
        )
        partial_user = self._add_user(
            email="partial@example.com",
            sub="sub-partial",
        )

        self._add_jira_mapping(jira_user)
        self._add_slack_mapping(jira_user)
        self._add_github_mapping(jira_user)
        self._add_channel_talk_mapping(jira_user)

        self._add_confluence_mapping(confluence_user)
        self._add_slack_mapping(confluence_user)
        self._add_github_mapping(confluence_user)
        self._add_channel_talk_mapping(confluence_user)

        self._add_confluence_mapping(partial_user)
        self._add_github_mapping(partial_user)
        self.db.commit()

        response = self.client.get(
            "/api/v1/integrations/user-source-mapping",
            params={"mapping_status": "full", "page": 1, "size": 50},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(
            {item["email"] for item in payload["items"]},
            {"confluence-full@example.com", "jira-full@example.com"},
        )
        confluence_item = next(
            item
            for item in payload["items"]
            if item["email"] == "confluence-full@example.com"
        )
        self.assertEqual(
            confluence_item["atlassian"]["identifier"],
            "confluence-full@example.com",
        )

    def test_mapping_status_partial_returns_users_missing_any_mapping_group(self) -> None:
        full_user = self._add_user(email="full@example.com", sub="sub-full")
        partial_user = self._add_user(email="partial@example.com", sub="sub-partial")

        self._add_jira_mapping(full_user)
        self._add_slack_mapping(full_user)
        self._add_github_mapping(full_user)
        self._add_channel_talk_mapping(full_user)

        self._add_jira_mapping(partial_user)
        self._add_github_mapping(partial_user)
        self.db.commit()

        response = self.client.get(
            "/api/v1/integrations/user-source-mapping",
            params={"mapping_status": "partial", "page": 1, "size": 50},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "partial@example.com")

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
