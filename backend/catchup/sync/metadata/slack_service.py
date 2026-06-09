import logging
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from typing import Any

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.connectors.slack.auth import get_slack_oauth_service
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.connectors.slack.client import SlackRateLimitError
from catchup.connectors.slack.schemas import SlackChannel
from catchup.connectors.slack.schemas import SlackUser
from catchup.connectors.slack.schemas import SlackUserProfile
from catchup.connectors.slack.schemas import SlackWorkspace
from catchup.db.engine import SessionLocal
from catchup.db.slack import domain_repository
from catchup.db.slack import oauth_repository as slack_crud
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SlackMetadataSnapshot:
    workspace: SlackWorkspace
    users: list[SlackUserProfile] = field(default_factory=list)
    channels: list[SlackChannel] = field(default_factory=list)
    channel_members: dict[str, list[str]] = field(default_factory=dict)


class SlackMetadataFormatter:
    def parse_channel(self, data: dict[str, Any]) -> SlackChannel:
        channel_id = data.get("id", "")
        name = data.get("name", channel_id)

        if data.get("is_im"):
            channel_type = "dm"
        elif data.get("is_mpim"):
            channel_type = "mpim"
        elif data.get("is_private"):
            channel_type = "private"
        else:
            channel_type = "public"

        created_ts = data.get("created", 0)
        created_at = (
            datetime.fromtimestamp(created_ts, tz=timezone.utc)
            if created_ts
            else datetime.now(timezone.utc)
        )

        return SlackChannel(
            id=channel_id,
            name=name,
            channel_type=channel_type,
            topic=data.get("topic", {}).get("value"),
            purpose=data.get("purpose", {}).get("value"),
            creator_id=data.get("creator"),
            member_count=data.get("num_members", 0),
            member_ids=[],
            is_archived=data.get("is_archived", False),
            is_private=data.get("is_private", False),
            is_member=data.get("is_member", False),
            is_mpim=data.get("is_mpim", False),
            is_im=data.get("is_im", False),
            created_at=created_at,
            updated_at=None,
        )

    def parse_user(self, data: dict[str, Any]) -> SlackUserProfile:
        profile = data.get("profile", {})
        updated_ts = data.get("updated", 0)
        updated_at = (
            datetime.fromtimestamp(updated_ts, tz=timezone.utc)
            if updated_ts
            else None
        )

        return SlackUserProfile(
            id=data.get("id", ""),
            team_id=data.get("team_id"),
            name=data.get("name", ""),
            real_name=profile.get("real_name") or data.get("real_name"),
            display_name=profile.get("display_name"),
            email=profile.get("email"),
            title=profile.get("title"),
            phone=profile.get("phone"),
            status_text=profile.get("status_text"),
            status_emoji=profile.get("status_emoji"),
            tz=data.get("tz"),
            tz_label=data.get("tz_label"),
            is_bot=data.get("is_bot", False),
            is_admin=data.get("is_admin", False),
            is_owner=data.get("is_owner", False),
            is_primary_owner=data.get("is_primary_owner", False),
            is_restricted=data.get("is_restricted", False),
            is_ultra_restricted=data.get("is_ultra_restricted", False),
            deleted=data.get("deleted", False),
            avatar_url=profile.get("image_512") or profile.get("image_192"),
            custom_fields=profile.get("fields", {}),
            updated_at=updated_at,
        )

    def parse_workspace(self, data: dict[str, Any]) -> SlackWorkspace:
        team = data.get("team", data)
        return SlackWorkspace(
            id=team.get("id", ""),
            name=team.get("name", ""),
            domain=team.get("domain", ""),
            url=f"https://{team.get('domain', '')}.slack.com/",
            email_domain=team.get("email_domain"),
            icon_url=team.get("icon", {}).get("image_132"),
            enterprise_id=team.get("enterprise_id"),
            enterprise_name=team.get("enterprise_name"),
        )


class SlackMetadataService:
    """
    Slack 설치 직후 메타데이터(Workspace/Users/Channels/Members) 동기화 서비스.
    """

    def __init__(
        self,
        *,
        team_id: str,
        access_token: str,
    ) -> None:
        self.team_id = team_id
        self.client = SlackApiClientWrapper(access_token, team_id)
        self.user_cache: dict[str, SlackUser] = {}
        self.last_channels: list[SlackChannel] = []
        self.formatter: SlackMetadataFormatter | None = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self.formatter = SlackMetadataFormatter()
        self._initialized = True
        logger.info("[SLACK][METADATA] Service initialized: team_id=%s", self.team_id)

    def _ensure_initialized(self) -> None:
        if not self._initialized or self.formatter is None:
            raise RuntimeError(
                "SlackMetadataService not initialized. "
                "Call await service.initialize() first."
            )

    def _persist_snapshot_db(
        self,
        snapshot: SlackMetadataSnapshot,
    ) -> None:
        with SessionLocal() as db:
            try:
                self._persist_snapshot(
                    db,
                    snapshot,
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

    def _persist_channel_snapshot_db(
        self,
        channels: list[SlackChannel],
    ) -> None:
        with SessionLocal() as db:
            try:
                self._persist_channel_snapshot(
                    db,
                    channels,
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

    def _persist_snapshot(
        self,
        db: Session,
        snapshot: SlackMetadataSnapshot,
    ) -> None:
        domain_repository.upsert_workspace(
            db,
            snapshot.workspace,
        )
        if snapshot.users:
            domain_repository.upsert_users_bulk(
                db,
                self.team_id,
                snapshot.users,
            )

        sync_result = domain_repository.sync_channels_snapshot(
            db,
            self.team_id,
            snapshot.channels,
        )
        logger.info(
            "[SLACK][INSTALLATION][METADATA] Channel snapshot synced: team_id=%s, upserted=%s, deleted=%s, deleted_members=%s",
            self.team_id,
            sync_result["upserted"],
            sync_result["deleted"],
            sync_result["deleted_members"],
        )

        domain_repository.delete_channel_members_by_team(
            db,
            self.team_id,
        )

        for channel in snapshot.channels:
            domain_repository.replace_channel_members(
                db,
                self.team_id,
                channel.id,
                snapshot.channel_members.get(channel.id, []),
            )

    def _persist_channel_snapshot(
        self,
        db: Session,
        channels: list[SlackChannel],
    ) -> None:
        sync_result = domain_repository.sync_channels_snapshot(
            db,
            self.team_id,
            channels,
        )
        logger.info(
            "[SLACK][TARGETS][METADATA] Channel snapshot synced: team_id=%s, upserted=%s, deleted=%s, deleted_members=%s",
            self.team_id,
            sync_result["upserted"],
            sync_result["deleted"],
            sync_result["deleted_members"],
        )

    async def _collect_snapshot(
        self,
        *,
        raise_on_error: bool = False,
    ) -> tuple[SlackMetadataSnapshot, dict[str, dict[str, int]]]:
        self._ensure_initialized()

        logger.info("[SLACK][INSTALLATION][METADATA] Sync started: team_id=%s", self.team_id)

        results: dict[str, dict[str, int]] = {
            "workspace": {"synced": 0, "errors": 0},
            "users": {"synced": 0, "errors": 0},
            "channels": {"synced": 0, "errors": 0},
        }

        workspace = await self._collect_workspace()
        results["workspace"]["synced"] = 1

        users = await self._collect_users()
        results["users"]["synced"] = len(users)

        channels, channel_members = await self._collect_channels()
        results["channels"]["synced"] = len(channels)

        snapshot = SlackMetadataSnapshot(
            workspace=workspace,
            users=users,
            channels=channels,
            channel_members=channel_members,
        )
        self.last_channels = channels

        if raise_on_error and any(section["errors"] > 0 for section in results.values()):
            raise RuntimeError(
                f"slack metadata refresh failed: team_id={self.team_id}, results={results}"
            )

        logger.info(
            "[SLACK][INSTALLATION][METADATA] Snapshot collected: team_id=%s, workspace_synced=%s, users_synced=%s, channels_synced=%s",
            self.team_id,
            results["workspace"]["synced"],
            results["users"]["synced"],
            results["channels"]["synced"],
        )
        return snapshot, results

    async def sync_metadata(
        self,
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, int]]:
        try:
            snapshot, results = await self._collect_snapshot(
                raise_on_error=raise_on_error,
            )
            await run_in_threadpool(
                self._persist_snapshot_db,
                snapshot,
            )
            return results
        except Exception as exc:
            logger.error(
                "[SLACK][INSTALLATION][METADATA] Sync failed: team_id=%s, error=%s",
                self.team_id,
                exc,
                exc_info=True,
            )
            raise

    async def _collect_target_channels(self) -> list[SlackChannel]:
        self._ensure_initialized()
        channels = await self._fetch_channels()
        self.last_channels = channels
        logger.info(
            "[SLACK][TARGETS][METADATA] Channels collected: team_id=%s, channel_count=%s",
            self.team_id,
            len(channels),
        )
        return channels

    async def sync_target_channels(self) -> list[SlackChannel]:
        channels = await self._collect_target_channels()
        await run_in_threadpool(
            self._persist_channel_snapshot_db,
            channels,
        )
        return channels

    async def _collect_workspace(self) -> SlackWorkspace:
        response = await self.client.get_team_info()
        return self.formatter.parse_workspace(response)

    async def _collect_users(self) -> list[SlackUserProfile]:
        users: list[SlackUserProfile] = []
        cursor = None

        while True:
            response = await self.client.list_users(cursor=cursor)
            members = response.get("members", [])

            for member in members:
                users.append(self.formatter.parse_user(member))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        self.user_cache.clear()
        self.user_cache.update(
            {
                user.id: SlackUser(
                    id=user.id,
                    name=user.name,
                    real_name=user.real_name,
                    display_name=user.display_name,
                )
                for user in users
                if not user.deleted
            }
        )
        return users

    async def _collect_channels(self) -> tuple[list[SlackChannel], dict[str, list[str]]]:
        channels = await self._fetch_channels()
        members = {
            channel.id: await self._fetch_channel_members(channel.id)
            for channel in channels
        }
        return channels, members

    async def _fetch_channels(self) -> list[SlackChannel]:
        channels: list[SlackChannel] = []
        cursor = None

        while True:
            response = await self.client.list_conversations(
                types="public_channel,private_channel",
                cursor=cursor,
            )
            for channel_data in response.get("channels", []):
                channels.append(self.formatter.parse_channel(channel_data))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return channels

    async def _fetch_channel_members(self, channel_id: str) -> list[str]:
        member_ids: list[str] = []
        cursor = None

        while True:
            response = await self.client.get_conversation_members(
                channel=channel_id,
                cursor=cursor,
            )
            member_ids.extend(response.get("members", []))
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return member_ids


def _load_token_db(team_id: str):
    with SessionLocal() as db:
        return slack_crud.get_slack_token_by_team_id(db, team_id)


async def _resolve_access_token(
    team_id: str,
    token_record=None,
) -> str:
    if token_record is None:
        token_record = await run_in_threadpool(_load_token_db, team_id)
    if not token_record:
        raise SyncConnectorException(
            f"Slack 연결을 찾을 수 없습니다: {team_id}",
            metadata={"team_id": team_id},
        )

    slack_service = get_slack_oauth_service()
    try:
        return await slack_service.get_valid_access_token(token_record)
    except SlackRateLimitError:
        raise
    except SlackConnectorApiError as exc:
        error_cls = (
            SyncInternalException
            if exc.status_code is not None and exc.status_code >= 500
            else SyncConnectorException
        )
        raise error_cls(
            exc.message,
            metadata={"team_id": team_id, **exc.metadata},
        ) from exc
    except HTTPException as exc:
        message = (
            exc.detail
            if isinstance(exc.detail, str)
            else "Slack 인증 정보를 확인할 수 없습니다"
        )
        error_cls = SyncInternalException if exc.status_code >= 500 else SyncConnectorException
        raise error_cls(
            message,
            metadata={"team_id": team_id},
        ) from exc
    except Exception as exc:
        logger.error(
            "[SLACK][METADATA] Failed to resolve access token: team_id=%s, error=%s",
            team_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "Slack access token 획득 중 오류가 발생했습니다",
            metadata={"team_id": team_id},
        ) from exc


async def create_slack_metadata_service(
    team_id: str,
) -> SlackMetadataService:
    access_token = await _resolve_access_token(team_id)

    try:
        service = SlackMetadataService(
            team_id=team_id,
            access_token=access_token,
        )
        await service.initialize()
        return service
    except Exception as exc:
        logger.error(
            "[SLACK][METADATA] Failed to initialize metadata service: team_id=%s, error=%s",
            team_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "Slack metadata service 초기화에 실패했습니다",
            metadata={"team_id": team_id},
        ) from exc
