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

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.schemas import (
    SlackThreadReply,
    SlackUser,
)
from catchup.connectors.slack.transformers import SlackTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.summarizer import SummarizerService, SummarizeRequest, get_summarizer_service
from catchup.configs.config import settings
from catchup.db.models import SlackEntityType, SlackSyncStatus
from catchup.db.slack import sync_repository as slack_sync
from catchup.db.slack import domain_repository as slack_entities

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

    def __init__(
        self,
        team_id: str,
        access_token: str,
        enable_summarization: bool = True,
    ):
        """
        SlackIngestionService 초기화

        Args:
            team_id: Slack Team/Workspace ID
            access_token: Slack Bot Access Token
            enable_summarization: 임베딩 전 LLM 요약 활성화 여부
        """
        self.team_id = team_id
        self.enable_summarization = enable_summarization
        self.client = SlackApiClientWrapper(access_token, team_id)
        self.transformer: SlackTransformer | None = None
        self.repository = PGVectorRepository()
        self.summarizer: SummarizerService | None = None
        self.user_cache: dict[str, SlackUser] = {}
        self.workspace_domain: str | None = None  # Permalink 생성용
        self._initialized = False

    async def initialize(self) -> None:
        """
        서비스 초기화

        PGVector Repository 초기화.
        User 캐시는 _sync_all_users()에서 갱신됨.
        """
        if self._initialized:
            return

        logger.info(f"Initializing SlackIngestionService for team_id={self.team_id}")

        # Transformer 생성 (user_cache는 _sync_all_users에서 in-place 갱신)
        self.transformer = SlackTransformer(self.user_cache)

        # Summarizer 초기화 (요약 활성화 시)
        if self.enable_summarization:
            self.summarizer = get_summarizer_service()
            logger.info("Summarization enabled for embedding optimization")

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

    def _build_permalink(self, channel_id: str, ts: str) -> str | None:
        """
        메시지 Permalink 생성 (API 호출 없이)

        Format: https://{domain}.slack.com/archives/{channel_id}/p{ts without dot}
        """
        if not self.workspace_domain:
            return None
        ts_clean = ts.replace(".", "")
        return f"https://{self.workspace_domain}.slack.com/archives/{channel_id}/p{ts_clean}"

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

        # 기본값: 최근 3년
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
    # 내부 동기화 메서드
    # ================================================================

    async def _sync_workspace(self, db: Session) -> dict[str, int]:
        """Workspace 동기화 (RDBMS 저장)"""
        try:
            slack_sync.create_or_update_sync_state(
                db, self.team_id, SlackEntityType.WORKSPACE,
                SlackSyncStatus.IN_PROGRESS
            )

            response = await self.client.get_team_info()
            workspace = self.transformer.parse_workspace(response)

            # Permalink 생성용 domain 저장
            self.workspace_domain = workspace.domain

            # RDBMS에 저장
            slack_entities.upsert_workspace(db, workspace)

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
        """모든 User를 RDBMS에 저장 + 캐시 갱신"""
        try:
            slack_sync.create_or_update_sync_state(
                db, self.team_id, SlackEntityType.USER,
                SlackSyncStatus.IN_PROGRESS
            )

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

            # RDBMS에 벌크 저장
            if users:
                slack_entities.upsert_users_bulk(db, self.team_id, users)

            # 캐시 갱신 (in-place 업데이트 - Transformer 참조 유지)
            self.user_cache.clear()
            self.user_cache.update({
                u.id: SlackUser(
                    id=u.id,
                    name=u.name,
                    real_name=u.real_name,
                    display_name=u.display_name,
                )
                for u in users
                if not u.deleted
            })
            logger.info(f"User cache refreshed: {len(self.user_cache)} users")

            slack_sync.mark_sync_completed(
                db, self.team_id, SlackEntityType.USER, len(users)
            )
            return {"synced": len(users), "errors": 0}

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

            channels = []

            cursor = None
            while True:
                response = await self.client.list_conversations(
                    types="public_channel,private_channel,mpim,im",
                    cursor=cursor,
                )
                channels_response = response.get("channels", [])

                for channel_data in channels_response:
                    if channel_ids and channel_data.get("id") not in channel_ids:
                        continue
                    channels.append(self.transformer.parse_channel(channel_data))

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            # RDBMS에 벌크 저장
            if channels:
                slack_entities.upsert_channels_bulk(db, self.team_id, channels)

            slack_sync.mark_sync_completed(
                db, self.team_id, SlackEntityType.CHANNEL, len(channels)
            )
            return {"synced": len(channels), "errors": 0}

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
                    db,
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
        db: Session,
        channel_id: str,
        channel_name: str,
        oldest: str | None,
        latest: str | None,
    ) -> dict[str, int]:
        """
        단일 채널의 메시지 동기화 (채널별 상태 추적)

        재시도 로직:
        - 이전 동기화가 실패했으면 last_successful_sync_at 기준으로 재시도
        - 성공 시 last_successful_sync_at 갱신
        - Upsert 패턴으로 중복 안전
        """
        errors = 0
        synced_count = 0

        # 접근 불가 채널 에러 코드 (에러가 아닌 스킵으로 처리)
        SKIPPABLE_ERRORS = {"not_in_channel", "channel_not_found", "missing_scope"}

        # 채널 동기화 상태 조회 및 effective_oldest 계산
        channel_state = slack_sync.get_channel_sync_state(db, self.team_id, channel_id)
        effective_oldest = oldest

        if channel_state and channel_state.last_successful_sync_at:
            # synced_count > 0: 실제로 메시지를 동기화한 적 있음 → 재시도 지원
            # synced_count == 0: 스킵되었거나 메시지가 없었음 → 전체 동기화 필요
            if channel_state.synced_count > 0:
                prev_oldest_ts = str(channel_state.last_successful_sync_at.timestamp())

                # oldest가 지정되지 않았거나, 이전 성공 시점이 더 최신이면 사용
                if oldest is None or float(prev_oldest_ts) > float(oldest):
                    effective_oldest = prev_oldest_ts
                    logger.info(
                        f"Channel {channel_name}: resuming from last_successful_sync_at "
                        f"({channel_state.last_successful_sync_at})"
                    )
            else:
                # 이전에 스킵되었던 채널 - 권한이 생겼을 수 있으므로 전체 동기화
                logger.info(
                    f"Channel {channel_name}: previously skipped (synced_count=0), "
                    f"attempting full sync from oldest={oldest}"
                )

        # 채널 동기화 시작 상태 기록
        slack_sync.start_channel_sync(
            db, self.team_id, channel_id, channel_name, effective_oldest
        )

        try:
            cursor = None
            while True:
                try:
                    response = await self.client.get_conversation_history(
                        channel=channel_id,
                        oldest=effective_oldest,
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
                        # 스킵된 채널도 성공으로 처리 (다음 동기화에서 다시 시도하지 않음)
                        slack_sync.mark_channel_sync_completed(
                            db, self.team_id, channel_id, 0
                        )
                        return {"synced": 0, "errors": 0, "skipped": True}
                    raise

                messages = response.get("messages", [])
                batch_documents = []
                batch_doc_ids = []

                for msg_data in messages:
                    try:
                        # Thread Parent인 경우 Replies 조회
                        replies = []
                        if msg_data.get("reply_count", 0) > 0:
                            replies = await self._fetch_thread_replies(
                                channel_id, msg_data.get("ts")
                            )

                        # Permalink 생성 (API 호출 없이)
                        permalink = self._build_permalink(
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
                        batch_documents.append(doc)
                        batch_doc_ids.append(doc.id)

                    except Exception as e:
                        logger.warning(
                            f"Failed to process message {msg_data.get('ts')}: {e}"
                        )
                        errors += 1

                # 배치 저장 및 진행 상황 업데이트
                if batch_documents:
                    if self.summarizer:
                        batch_documents = await self._summarize_documents(batch_documents)
                    await self.repository.upsert_documents(batch_documents, batch_doc_ids)
                    synced_count += len(batch_documents)

                    # 배치 완료 시 진행 상황 기록 (마지막 메시지 ts 포함)
                    latest_ts = messages[-1].get("ts") if messages else None
                    slack_sync.update_channel_sync_progress(
                        db, self.team_id, channel_id, synced_count, latest_ts
                    )

                if not response.get("has_more"):
                    break
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            # 채널 동기화 완료
            slack_sync.mark_channel_sync_completed(
                db, self.team_id, channel_id, synced_count
            )

            logger.debug(
                f"Channel {channel_name}: synced {synced_count} messages, "
                f"{errors} errors"
            )
            return {"synced": synced_count, "errors": errors}

        except Exception as e:
            logger.error(f"Channel {channel_name} message sync failed: {e}")
            # 실패 시 상태 기록 (last_successful_sync_at은 유지됨)
            slack_sync.mark_channel_sync_failed(
                db, self.team_id, channel_id, str(e)[:1000], synced_count
            )
            return {"synced": synced_count, "errors": errors + 1}

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

    async def _summarize_documents(
        self,
        documents: list[Document],
    ) -> list[Document]:
        """
        문서들의 page_content를 LLM으로 요약하여 교체

        contextual_content(구조화된 정보 포함)를 요약 입력으로 사용하여
        더 풍부한 컨텍스트 기반 요약 생성.

        Args:
            documents: 요약할 Document 리스트

        Returns:
            page_content가 요약된 Document 리스트
        """
        if not self.summarizer or not documents:
            return documents

        # SummarizeRequest 리스트 생성 (source + entity_type → source_type)
        requests = []
        for doc in documents:
            content = doc.metadata.get("contextual_content", doc.page_content)
            entity_type = doc.metadata.get("entity_type", "message")
            source_type = f"slack_{entity_type}"  # slack_message
            requests.append(SummarizeRequest(content=content, source_type=source_type))

        # 일괄 요약
        summarized = await self.summarizer.summarize_batch(requests)

        # 요약된 텍스트로 교체
        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(f"Summarized {len(documents)} documents for embedding")
        return documents

