import logging

from sqlalchemy.orm import Session

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.schemas import SlackUser
from catchup.connectors.slack.transformers import SlackTransformer
from catchup.db.slack import domain_repository

logger = logging.getLogger(__name__)


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

    async def sync_metadata(
        self,
        db: Session,
        *,
        auto_commit: bool = True,
        rollback_on_error: bool = True,
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, int]]:
        """
        설치 직후 Slack 메타데이터를 일괄 동기화한다.
        """
        self._ensure_initialized()

        logger.info("[SLACK][INSTALLATION][METADATA] Sync started: team_id=%s", self.team_id)

        results: dict[str, dict[str, int]] = {
            "workspace": {"synced": 0, "errors": 0},
            "users": {"synced": 0, "errors": 0},
            "channels": {"synced": 0, "errors": 0},
        }

        try:
            results["workspace"] = await self._sync_workspace(
                db,
                auto_commit=auto_commit,
                rollback_on_error=rollback_on_error,
            )
            if raise_on_error and results["workspace"]["errors"] > 0:
                raise RuntimeError(
                    f"slack workspace metadata refresh failed: team_id={self.team_id}"
                )

            results["users"] = await self._sync_all_users(
                db,
                auto_commit=auto_commit,
                rollback_on_error=rollback_on_error,
            )
            if raise_on_error and results["users"]["errors"] > 0:
                raise RuntimeError(
                    f"slack user metadata refresh failed: team_id={self.team_id}"
                )

            results["channels"] = await self._sync_all_channels(
                db,
                auto_commit=auto_commit,
                rollback_on_error=rollback_on_error,
            )
            if raise_on_error and results["channels"]["errors"] > 0:
                raise RuntimeError(
                    f"slack channel metadata refresh failed: team_id={self.team_id}"
                )

            logger.info(
                "[SLACK][INSTALLATION][METADATA] Sync completed: team_id=%s, workspace_synced=%s, users_synced=%s, channels_synced=%s",
                self.team_id,
                results["workspace"]["synced"],
                results["users"]["synced"],
                results["channels"]["synced"],
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

    async def _sync_workspace(
        self,
        db: Session,
        *,
        auto_commit: bool = True,
        rollback_on_error: bool = True,
    ) -> dict[str, int]:
        try:
            response = await self.client.get_team_info()
            workspace = self.transformer.parse_workspace(response)
            domain_repository.upsert_workspace(
                db,
                workspace,
                auto_commit=auto_commit,
            )
            return {"synced": 1, "errors": 0}
        except Exception as exc:
            logger.error(
                "[SLACK][INSTALLATION][METADATA] Workspace sync failed: team_id=%s, error=%s",
                self.team_id,
                exc,
                exc_info=True,
            )
            if rollback_on_error:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_all_users(
        self,
        db: Session,
        *,
        auto_commit: bool = True,
        rollback_on_error: bool = True,
    ) -> dict[str, int]:
        try:
            users = []
            cursor = None

            while True:
                response = await self.client.list_users(cursor=cursor)
                members = response.get("members", [])

                for member in members:
                    users.append(self.transformer.parse_user(member))

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            if users:
                domain_repository.upsert_users_bulk(
                    db,
                    self.team_id,
                    users,
                    auto_commit=auto_commit,
                )

            # Transformer가 참조하는 캐시를 설치 시점에도 최신화한다.
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

            return {"synced": len(users), "errors": 0}
        except Exception as exc:
            logger.error(
                "[SLACK][INSTALLATION][METADATA] User sync failed: team_id=%s, error=%s",
                self.team_id,
                exc,
                exc_info=True,
            )
            if rollback_on_error:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_all_channels(
        self,
        db: Session,
        *,
        auto_commit: bool = True,
        rollback_on_error: bool = True,
    ) -> dict[str, int]:
        try:
            channels = []
            cursor = None

            while True:
                response = await self.client.list_conversations(
                    types="public_channel,private_channel,mpim,im",
                    cursor=cursor,
                )
                for channel_data in response.get("channels", []):
                    channels.append(self.transformer.parse_channel(channel_data))

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            sync_result = domain_repository.sync_channels_snapshot(
                db,
                self.team_id,
                channels,
                auto_commit=auto_commit,
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
                auto_commit=auto_commit,
            )

            for channel in channels:
                await self._sync_channel_members(
                    db,
                    channel.id,
                    auto_commit=auto_commit,
                )

            return {"synced": len(channels), "errors": 0}
        except Exception as exc:
            logger.error(
                "[SLACK][INSTALLATION][METADATA] Channel sync failed: team_id=%s, error=%s",
                self.team_id,
                exc,
                exc_info=True,
            )
            if rollback_on_error:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_channel_members(
        self,
        db: Session,
        channel_id: str,
        *,
        auto_commit: bool = True,
    ) -> None:
        try:
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

            domain_repository.replace_channel_members(
                db,
                self.team_id,
                channel_id,
                member_ids,
                auto_commit=auto_commit,
            )
        except Exception as exc:
            logger.warning(
                "[SLACK][INSTALLATION][METADATA] Member sync skipped: team_id=%s, channel_id=%s, error=%s",
                self.team_id,
                channel_id,
                exc,
            )
