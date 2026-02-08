"""
Slack 데이터 동기화 서비스

Slack API에서 데이터를 가져와 PGVector에 저장하는 서비스.
SlackApiClientWrapper, SlackTransformer, PGVectorRepository를 조합.

사용법:
    # 초기화
    service = SlackIngestionService(team_id, access_token)
    await service.initialize()

    # 전체 동기화
    await service.full_sync(db, oldest="1704067200.000000")

    # 증분 동기화
    await service.incremental_sync(db)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.documents import Document
from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import Session

from catchup.components.connectors.slack.client import SlackApiClientWrapper
from catchup.components.connectors.slack.schemas import (
    SlackThreadReply,
    SlackUser,
)
from catchup.components.connectors.slack.transformers import SlackTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.configs.config import settings
from catchup.db.models import SlackEntityType, SlackSyncStatus, SlackChannelType
from catchup.db import slack_sync
from catchup.db import slack_entities

logger = logging.getLogger(__name__)


class SlackIngestionService:
    """
    Slack 데이터 동기화 서비스

    Attributes:
        client: Slack API 클라이언트
        transformer: Slack 엔티티 → LangChain Document 변환기
        repository: PGVector 벡터 저장소
        team_id: Slack Team/Workspace ID
        user_cache: user_id → SlackUser 캐시
    """

    def __init__(self, team_id: str, access_token: str):
        """
        SlackIngestionService 초기화

        Args:
            team_id: Slack Team/Workspace ID
            access_token: Slack Bot Access Token
        """
        self.team_id = team_id
        self.client = SlackApiClientWrapper(access_token, team_id)
        self.transformer: SlackTransformer | None = None
        self.repository = PGVectorRepository()
        self.user_cache: dict[str, SlackUser] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """
        서비스 초기화

        User 캐시 빌드 및 PGVector Repository 초기화.
        동기화 작업 전에 반드시 호출해야 함.
        """
        if self._initialized:
            return

        logger.info(f"Initializing SlackIngestionService for team_id={self.team_id}")

        # User 캐시 빌드 (멘션 변환용)
        await self._build_user_cache()

        # Transformer 생성
        self.transformer = SlackTransformer(self.user_cache)

        # PGVector 초기화
        await self.repository.initialize()

        self._initialized = True
        logger.info("SlackIngestionService initialized successfully")

    def _ensure_initialized(self) -> None:
        """초기화 확인"""
        if not self._initialized or self.transformer is None:
            raise RuntimeError(
                "SlackIngestionService not initialized. "
                "Call await service.initialize() first."
            )

    # ================================================================
    # 전체 동기화 (Full Sync)
    # ================================================================

    async def full_sync(
        self,
        db: Session,
        oldest: str | None = None,
        latest: str | None = None,
        channel_ids: list[str] | None = None,
        sync_messages: bool = True,
        sync_channels: bool = True,
        sync_users: bool = True,
        sync_workspace: bool = True,
    ) -> dict[str, Any]:
        """
        전체 동기화

        저장소 분리:
        - Message: PGVector (Vector Store) - 시맨틱 검색용
        - Workspace, Channel, User: RDBMS - 정적 참조 데이터
        - File: Message에 통합 (message_type="file_share")

        Args:
            db: SQLAlchemy Session
            oldest: 시작 Slack timestamp (이 시간 이후 메시지만)
            latest: 종료 Slack timestamp (이 시간 이전 메시지만)
            channel_ids: 특정 채널만 동기화 (None이면 전체)
            sync_messages: 메시지 동기화 여부
            sync_channels: 채널 동기화 여부
            sync_users: 사용자 동기화 여부
            sync_workspace: 워크스페이스 동기화 여부

        Returns:
            동기화 결과 통계
        """
        self._ensure_initialized()

        # 기본값: 최근 N일
        if oldest is None:
            days_ago = datetime.now(timezone.utc) - timedelta(days=settings.SLACK_DEFAULT_SYNC_DAYS)
            oldest = str(days_ago.timestamp())

        logger.info(
            f"Starting full sync for team_id={self.team_id}, "
            f"oldest={oldest}, latest={latest}, "
            f"channel_ids={channel_ids or 'all'}"
        )

        results = {
            "messages": {"synced": 0, "errors": 0},
            "channels": {"synced": 0, "errors": 0},
            "users": {"synced": 0, "errors": 0},
            "workspace": {"synced": 0, "errors": 0},
        }

        try:
            # 1. Workspace 동기화 (RDBMS)
            if sync_workspace:
                workspace_result = await self._sync_workspace(db)
                results["workspace"]["synced"] = workspace_result.get("synced", 0)
                results["workspace"]["errors"] = workspace_result.get("errors", 0)

            # 2. User 동기화 (RDBMS)
            if sync_users:
                user_result = await self._sync_all_users(db)
                results["users"]["synced"] = user_result.get("synced", 0)
                results["users"]["errors"] = user_result.get("errors", 0)

            # 3. Channel 동기화 (RDBMS)
            if sync_channels:
                channel_result = await self._sync_all_channels(db, channel_ids)
                results["channels"]["synced"] = channel_result.get("synced", 0)
                results["channels"]["errors"] = channel_result.get("errors", 0)

            # 4. Message 동기화 (Vector Store) - File은 message_type="file_share"로 포함
            if sync_messages:
                message_result = await self._sync_all_messages(
                    db, oldest, latest, channel_ids
                )
                results["messages"]["synced"] = message_result.get("synced", 0)
                results["messages"]["errors"] = message_result.get("errors", 0)

            logger.info(f"Full sync completed for team_id={self.team_id}: {results}")
            return results

        except Exception as e:
            logger.error(f"Full sync failed for team_id={self.team_id}: {e}")
            raise

    # ================================================================
    # 증분 동기화 (Incremental Sync)
    # ================================================================

    async def incremental_sync(
        self,
        db: Session,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        """
        증분 동기화 (마지막 동기화 이후 변경분만)

        Args:
            db: SQLAlchemy Session
            since: 이 시간 이후 변경분만 동기화 (None이면 마지막 성공 동기화 시간)

        Returns:
            동기화 결과 통계
        """
        self._ensure_initialized()

        # since 결정
        if since is None:
            message_state = slack_sync.get_sync_state(
                db, self.team_id, SlackEntityType.MESSAGE
            )
            if message_state and message_state.last_successful_sync_at:
                since = message_state.last_successful_sync_at
            else:
                logger.warning(
                    f"No previous sync found for team_id={self.team_id}, "
                    "running full sync instead"
                )
                return await self.full_sync(db)

        oldest = str(since.timestamp())

        logger.info(
            f"Starting incremental sync for team_id={self.team_id}, since={since}"
        )

        return await self.full_sync(
            db,
            oldest=oldest,
            sync_workspace=False,
            sync_channels=True,
            sync_users=True,
            sync_messages=True,
        )

    # ================================================================
    # 검색
    # ================================================================

    async def search(
        self,
        query: str,
        k: int = 5,
        entity_type: str | None = None,
        channel_id: str | None = None,
    ) -> list[Document]:
        """
        벡터 시맨틱 검색
        """
        self._ensure_initialized()

        filters = {"source": "slack", "team_id": self.team_id}
        if entity_type:
            filters["entity_type"] = entity_type
        if channel_id:
            filters["channel_id"] = channel_id

        return await self.repository.search(query, k=k, filter=filters)

    # ================================================================
    # 내부 동기화 메서드
    # ================================================================

    async def _build_user_cache(self) -> None:
        """모든 User 정보를 메모리에 캐싱"""
        logger.info(f"Building user cache for team_id={self.team_id}")

        cursor = None
        total = 0

        while True:
            response = await self.client.list_users(cursor=cursor)
            members = response.get("members", [])

            for member in members:
                if member.get("deleted"):
                    continue
                self.user_cache[member["id"]] = SlackUser(
                    id=member["id"],
                    name=member.get("name"),
                    real_name=member.get("real_name"),
                    display_name=member.get("profile", {}).get("display_name"),
                )
                total += 1

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        logger.info(f"User cache built: {total} users")

    async def _sync_workspace(self, db: Session) -> dict[str, int]:
        """Workspace 동기화 (RDBMS 저장)"""
        try:
            slack_sync.create_or_update_sync_state(
                db, self.team_id, SlackEntityType.WORKSPACE,
                SlackSyncStatus.IN_PROGRESS
            )

            response = await self.client.get_team_info()
            workspace = self.transformer.parse_workspace(response)

            # RDBMS에 저장
            slack_entities.upsert_workspace(
                db,
                workspace_id=workspace.id,
                name=workspace.name,
                domain=workspace.domain,
                url=workspace.url,
                email_domain=workspace.email_domain,
                icon_url=workspace.icon_url,
                enterprise_id=workspace.enterprise_id,
                enterprise_name=workspace.enterprise_name,
            )

            slack_sync.mark_sync_completed(db, self.team_id, SlackEntityType.WORKSPACE, 1)
            return {"synced": 1, "errors": 0}

        except Exception as e:
            logger.error(f"Workspace sync failed: {e}")
            db.rollback()  # 트랜잭션 롤백
            try:
                slack_sync.create_or_update_sync_state(
                    db, self.team_id, SlackEntityType.WORKSPACE,
                    SlackSyncStatus.FAILED, error=str(e)[:500]
                )
            except Exception:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_all_users(self, db: Session) -> dict[str, int]:
        """모든 User를 RDBMS에 저장"""
        try:
            slack_sync.create_or_update_sync_state(
                db, self.team_id, SlackEntityType.USER,
                SlackSyncStatus.IN_PROGRESS
            )

            users_data = []

            cursor = None
            while True:
                response = await self.client.list_users(cursor=cursor)
                members = response.get("members", [])

                for member in members:
                    user = self.transformer.parse_user(member)
                    users_data.append({
                        "team_id": self.team_id,
                        "user_id": user.id,
                        "name": user.name,
                        "real_name": user.real_name or user.name,
                        "display_name": user.display_name or user.name,
                        "deleted": user.deleted,
                        "email": user.email,
                        "avatar_url": user.avatar_url,
                        "title": user.title,
                        "phone": user.phone,
                        "tz": user.tz,
                        "tz_label": user.tz_label,
                        "is_bot": user.is_bot,
                        "is_admin": user.is_admin,
                        "is_owner": user.is_owner,
                        "is_restricted": user.is_restricted,
                        "updated_at": user.updated_at,
                    })

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            # RDBMS에 벌크 저장
            if users_data:
                slack_entities.upsert_users_bulk(db, users_data)

            slack_sync.mark_sync_completed(
                db, self.team_id, SlackEntityType.USER, len(users_data)
            )
            return {"synced": len(users_data), "errors": 0}

        except Exception as e:
            logger.error(f"User sync failed: {e}")
            db.rollback()  # 트랜잭션 롤백
            try:
                slack_sync.create_or_update_sync_state(
                    db, self.team_id, SlackEntityType.USER,
                    SlackSyncStatus.FAILED, error=str(e)[:500]
                )
            except Exception:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_all_channels(
        self,
        db: Session,
        channel_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """모든 Channel을 RDBMS에 저장"""
        try:
            slack_sync.create_or_update_sync_state(
                db, self.team_id, SlackEntityType.CHANNEL,
                SlackSyncStatus.IN_PROGRESS
            )

            channels_data = []

            cursor = None
            while True:
                response = await self.client.list_conversations(
                    types="public_channel,private_channel,mpim,im",
                    cursor=cursor,
                )
                channels = response.get("channels", [])

                for channel_data in channels:
                    channel_id = channel_data.get("id")
                    if channel_ids and channel_id not in channel_ids:
                        continue

                    channel = self.transformer.parse_channel(channel_data)
                    channels_data.append({
                        "id": channel.id,
                        "team_id": self.team_id,
                        "name": channel.name,
                        "channel_type": SlackChannelType(channel.channel_type),
                        "topic": channel.topic,
                        "purpose": channel.purpose,
                        "creator_id": channel.creator_id,
                        "member_count": channel.member_count,
                        "is_archived": channel.is_archived,
                        "is_private": channel.is_private,
                        "created_at": channel.created_at,
                    })

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            # RDBMS에 벌크 저장
            if channels_data:
                slack_entities.upsert_channels_bulk(db, channels_data)

            slack_sync.mark_sync_completed(
                db, self.team_id, SlackEntityType.CHANNEL, len(channels_data)
            )
            return {"synced": len(channels_data), "errors": 0}

        except Exception as e:
            logger.error(f"Channel sync failed: {e}")
            db.rollback()  # 트랜잭션 롤백
            try:
                slack_sync.create_or_update_sync_state(
                    db, self.team_id, SlackEntityType.CHANNEL,
                    SlackSyncStatus.FAILED, error=str(e)[:500]
                )
            except Exception:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_all_messages(
        self,
        db: Session,
        oldest: str | None,
        latest: str | None,
        channel_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """모든 채널의 Message 동기화"""
        try:
            slack_sync.create_or_update_sync_state(
                db, self.team_id, SlackEntityType.MESSAGE,
                SlackSyncStatus.IN_PROGRESS,
                oldest_ts=oldest,
                latest_ts=latest,
            )

            total_synced = 0
            total_errors = 0
            total_skipped = 0

            # 채널 목록 조회
            channels_to_sync = []
            cursor = None
            while True:
                response = await self.client.list_conversations(
                    types="public_channel,private_channel,mpim,im",
                    cursor=cursor,
                )
                for ch in response.get("channels", []):
                    ch_id = ch.get("id")
                    if channel_ids is None or ch_id in channel_ids:
                        channels_to_sync.append({
                            "id": ch_id,
                            "name": ch.get("name", ch_id),
                        })

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            logger.info(f"Syncing messages from {len(channels_to_sync)} channels")

            for channel in channels_to_sync:
                result = await self._sync_channel_messages(
                    channel["id"],
                    channel["name"],
                    oldest,
                    latest,
                )
                total_synced += result.get("synced", 0)
                total_errors += result.get("errors", 0)
                if result.get("skipped"):
                    total_skipped += 1

                slack_sync.update_sync_progress(
                    db, self.team_id, SlackEntityType.MESSAGE,
                    synced_count=total_synced
                )

            if total_skipped > 0:
                logger.info(
                    f"Message sync: {total_synced} synced, {total_errors} errors, "
                    f"{total_skipped} channels skipped (not_in_channel/missing_scope)"
                )

            slack_sync.mark_sync_completed(
                db, self.team_id, SlackEntityType.MESSAGE, total_synced
            )
            return {"synced": total_synced, "errors": total_errors, "skipped": total_skipped}

        except Exception as e:
            logger.error(f"Message sync failed: {e}")
            db.rollback()  # 트랜잭션 롤백
            try:
                slack_sync.create_or_update_sync_state(
                    db, self.team_id, SlackEntityType.MESSAGE,
                    SlackSyncStatus.FAILED, error=str(e)[:500]
                )
            except Exception:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_channel_messages(
        self,
        channel_id: str,
        channel_name: str,
        oldest: str | None,
        latest: str | None,
    ) -> dict[str, int]:
        """단일 채널의 메시지 동기화"""
        documents = []
        doc_ids = []
        errors = 0

        # 접근 불가 채널 에러 코드 (에러가 아닌 스킵으로 처리)
        SKIPPABLE_ERRORS = {"not_in_channel", "channel_not_found", "missing_scope"}

        try:
            cursor = None
            while True:
                try:
                    response = await self.client.get_conversation_history(
                        channel=channel_id,
                        oldest=oldest,
                        latest=latest,
                        cursor=cursor,
                        limit=settings.SLACK_MESSAGE_BATCH_SIZE,
                    )
                except SlackApiError as e:
                    error_code = e.response.get("error", "")
                    if error_code in SKIPPABLE_ERRORS:
                        logger.info(
                            f"Skipping channel {channel_name} ({channel_id}): {error_code}"
                        )
                        return {"synced": 0, "errors": 0, "skipped": True}
                    raise

                messages = response.get("messages", [])

                for msg_data in messages:
                    try:
                        # Thread Parent인 경우 Replies 조회
                        replies = []
                        if msg_data.get("reply_count", 0) > 0:
                            replies = await self._fetch_thread_replies(
                                channel_id, msg_data.get("ts")
                            )

                        # Permalink 조회
                        permalink = await self.client.get_permalink(
                            channel_id, msg_data.get("ts")
                        )

                        # 메시지 파싱 및 변환
                        message = self.transformer.parse_message(
                            msg_data,
                            channel_id,
                            channel_name,
                            permalink,
                            replies,
                        )
                        doc = self.transformer.transform_message(message, self.team_id)
                        documents.append(doc)
                        doc_ids.append(doc.id)

                    except Exception as e:
                        logger.warning(
                            f"Failed to process message {msg_data.get('ts')}: {e}"
                        )
                        errors += 1

                if not response.get("has_more"):
                    break
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            if documents:
                await self.repository.upsert_documents(documents, doc_ids)

            logger.debug(
                f"Channel {channel_name}: synced {len(documents)} messages, "
                f"{errors} errors"
            )
            return {"synced": len(documents), "errors": errors}

        except Exception as e:
            logger.error(f"Channel {channel_name} message sync failed: {e}")
            return {"synced": len(documents), "errors": errors + 1}

    async def _fetch_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> list[SlackThreadReply]:
        """Thread Replies 조회 및 파싱"""
        replies = []

        try:
            cursor = None
            while True:
                response = await self.client.get_conversation_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    cursor=cursor,
                )

                messages = response.get("messages", [])

                # 첫 번째 메시지는 Thread Parent이므로 제외
                for msg_data in messages[1:]:
                    reply = self.transformer.parse_reply(msg_data)
                    replies.append(reply)

                if not response.get("has_more"):
                    break
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        except Exception as e:
            logger.warning(f"Failed to fetch replies for {thread_ts}: {e}")

        return replies

