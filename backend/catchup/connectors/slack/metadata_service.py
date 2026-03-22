import logging
from dataclasses import dataclass, field

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.schemas import SlackChannel, SlackUser, SlackWorkspace
from catchup.connectors.slack.transformers import SlackTransformer
from catchup.db.engine import SessionLocal
from catchup.db.slack import domain_repository

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SlackMetadataSnapshot:
    workspace: SlackWorkspace
    users: list[SlackUser] = field(default_factory=list)
    channels: list[SlackChannel] = field(default_factory=list)
    channel_members: dict[str, list[str]] = field(default_factory=dict)


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
        self.transformer: SlackTransformer | None = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self.transformer = SlackTransformer(self.user_cache)
        self._initialized = True
        logger.info("[SLACK][METADATA] Service initialized: team_id=%s", self.team_id)

    def _ensure_initialized(self) -> None:
        if not self._initialized or self.transformer is None:
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
        return self.transformer.parse_workspace(response)

    async def _collect_users(self) -> list[SlackUser]:
        users: list[SlackUser] = []
        cursor = None

        while True:
            response = await self.client.list_users(cursor=cursor)
            members = response.get("members", [])

            for member in members:
                users.append(self.transformer.parse_user(member))

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
                channels.append(self.transformer.parse_channel(channel_data))

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
