import asyncio
from builtins import ExceptionGroup
import logging
from _collections_abc import AsyncGenerator
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
from catchup.db.slack import domain_repository as domain_repository

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
        repository: PGVectorRepository,
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
        self.repository = repository
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

    def _load_context_from_db(self, db: Session) -> None:
        """메시지 수집 전 DB에서 유저 캐시 + workspace domain 로드"""
        try:
            # User Cache
            users = domain_repository.get_users_by_team(db, self.team_id, include_deleted=True)
            self.user_cache.clear()
            self.user_cache.update({
                u.user_id: SlackUser(
                    id=u.user_id,
                    name=u.name,
                    real_name=u.real_name,
                    display_name=u.display_name,
                )
                for u in users
            })

            # Workspace Domain (Permalink 생성용)
            if not self.workspace_domain:
                workspace = domain_repository.get_workspace(db, self.team_id)
                if workspace:
                    self.workspace_domain = workspace.domain

            logger.info(
                f"Context loaded from DB: {len(self.user_cache)} users, "
                f"domain={self.workspace_domain}"
            )
        except Exception as e:
            logger.error(f"Failed to load context from DB: {e}", exc_info=True)

    # 수집 제외 subtype 목록 (봇, 채널 참여/퇴장 등 시스템 메시지)
    _SKIP_SUBTYPES = frozenset({
        "bot_message",
        "channel_join",
        "channel_leave",
        "group_join",
        "group_leave",
    })

    def _should_skip_message(self, msg_data: dict) -> bool:
        """수집 대상에서 제외할 메시지인지 판별"""
        if msg_data.get("bot_id"):
            return True
        if msg_data.get("subtype") in self._SKIP_SUBTYPES:
            return True
        text = msg_data.get("text", "")
        if len(text) <= 10:
            return True
        return False

    def _build_permalink(self, channel_id: str, ts: str) -> str | None:
        """
        메시지 Permalink 생성 (API 호출 없이)

        Format: https://{domain}.slack.com/archives/{channel_id}/p{ts without dot}
        """
        if not self.workspace_domain:
            return None
        ts_clean = ts.replace(".", "")
        return f"https://{self.workspace_domain}.slack.com/archives/{channel_id}/p{ts_clean}"
    
    async def sync_metadata(self, db:Session) -> dict[str, int]:
        """
        Slack App Installation 직후 메타데이터 동기화

        Workspace - Users - Channels - Channel Members
        """
        self._ensure_initialized()

        logger.info(f"[SLACK][INSTALLATION] Starting Metadata Sync for team_id : {self.team_id}")
        
        results = {
        "workspace": {"synced": 0, "errors": 0},
        "users": {"synced": 0, "errors": 0},
        "channels": {"synced": 0, "errors": 0},
        }

        try:
            workspace_result = await self._sync_workspace(db)
            results["workspace"] = workspace_result

            user_result = await self._sync_all_users(db)
            results["users"] = user_result

            channel_result = await self._sync_all_channels(db)
            results["channels"] = channel_result
    
            logger.info(f"[SLACK][INSTALLATION] Completed Metadata Sync for team_id : {self.team_id}")
            return results
        except Exception as e:
            logger.error(f"[SLACK][INSTALLATION] Failed Metadat Sync for team_id : {self.team_id}")
            raise
        

    # ================================================================
    # 전체 동기화 (Full Sync)
    # ================================================================

    async def full_sync(
            self,
            db: Session,
            sync_days: int | None = None,
    ) -> dict[str, Any]:
        """
        전체 동기화
        - 접근 가능한 채널을 순회하면서 메세지 수집
        """
        self._ensure_initialized()
        self._load_context_from_db(db)

        days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
        sync_from = str((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

        logger.info(f"[SLACK][FULL SYNC] Starting Full Sync for team_id : {self.team_id}, sync_days = {sync_days}")

        try:
            message_result = await self._sync_all_messages(db, sync_from)

            logger.info(f"[SLACK][FULL SYNC] Full Sync Completed for team_id : {self.team_id} :  {message_result}")
            return {"messages": message_result}

        except Exception as e:
            logger.error(f"[SLACK][FULL SYNC] Full Sync Failed for team_id : {self.team_id} : {e}")
            raise
    # ================================================================
    # Webhook Message Buffer Flush
    # ================================================================

    async def flush_message(
        self,
        db: Session,
        channel_ids: list[str],
    ) -> dict[str, Any]:
        """
        Webhook Flush — 버퍼링된 채널의 메시지를 마지막 동기화 시점부터 수집
        """
        self._ensure_initialized()
        self._load_context_from_db(db)

        logger.info(
            f"[SLACK][FLUSH] Starting for team_id={self.team_id}, "
            f"channels={len(channel_ids)}"
        )

        # 마지막 성공 동기화 시점 조회
        sync_state = slack_sync.get_sync_state(db, self.team_id, SlackEntityType.MESSAGE)
        if sync_state and sync_state.last_successful_sync_at:
            sync_from = str(sync_state.last_successful_sync_at.timestamp())
        else:
            sync_from = str((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp())

        total_synced = 0
        total_errors = 0
        
        for channel_id in channel_ids:
            channel = domain_repository.get_channel(db, channel_id)
            channel_name = channel.name if channel else channel_id

            result = await self._sync_channel_messages(
                channel_id, channel_name, sync_from, db,
            )
            total_synced += result.get("synced", 0)
            total_errors += result.get("errors", 0)

        logger.info(
            f"[SLACK][FLUSH] Completed for team_id={self.team_id}, "
            f"channels={len(channel_ids)}"
        )
        return {"messages": {"synced": total_synced, "errors": total_errors}}

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
            domain_repository.upsert_workspace(db, workspace)

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
                domain_repository.upsert_users_bulk(db, self.team_id, users)

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

    async def _sync_all_channels(self, db: Session) -> dict[str, int]:
        """모든 Channel을 RDBMS에 저장 + 채널별 멤버 수집"""
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
                for channel_data in response.get("channels", []):
                    channels.append(self.transformer.parse_channel(channel_data))

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            # RDBMS에 벌크 저장
            if channels:
                domain_repository.upsert_channels_bulk(db, self.team_id, channels)

            # 채널별 멤버 수집
            for channel in channels:
                await self._sync_channel_members(db, channel.id)

            slack_sync.mark_sync_completed(
                db, self.team_id, SlackEntityType.CHANNEL, len(channels)
            )
            return {"synced": len(channels), "errors": 0}

        except Exception as e:
            logger.error(f"Channel sync failed: {e}")
            db.rollback()
            try:
                slack_sync.create_or_update_sync_state(
                    db, self.team_id, SlackEntityType.CHANNEL,
                    SlackSyncStatus.FAILED, error=str(e)[:500]
                )
            except Exception:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_channel_members(self, db: Session, channel_id: str) -> None:
        """단일 채널의 멤버 목록 수집 → DB 저장"""
        try:
            member_ids = []
            cursor = None
            while True:
                response = await self.client.get_conversation_members(
                    channel=channel_id, cursor=cursor,
                )
                member_ids.extend(response.get("members", []))
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            domain_repository.replace_channel_members(db, self.team_id, channel_id, member_ids)
        except Exception as e:
            logger.warning(f"Failed to sync members for channel {channel_id}: {e}")

    async def _get_syncable_channels(self) -> list[dict[str, str]]:
        channels = []
        cursor = None

        while True:
            response = await self.client.list_conversations(
                types="public_channel,private_channel,mpim,im",
                cursor=cursor,
            )
            for channel in response.get("channels", []):
                channel_id = channel.get("id")
                channels.append({
                    "id": channel_id,
                    "name": channel.get("name", channel_id),
                })

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return channels

    async def _sync_all_messages(
        self,
        db: Session,
        sync_from: str | None,
    ) -> dict[str, int]:
        """모든 채널의 Message 동기화"""
        try:
            slack_sync.create_or_update_sync_state(
                db, self.team_id, SlackEntityType.MESSAGE,
                SlackSyncStatus.IN_PROGRESS,
                oldest_ts=sync_from,
            )

            channels_to_sync = await self._get_syncable_channels()
            logger.info(f"[SLACK][FULL SYNC] Syncing messages from {len(channels_to_sync)} channels")

            channel_semaphore = asyncio.Semaphore(settings.SLACK_CHANNEL_SYNC_CONCURRENCY)
            results = await asyncio.gather(
                *[
                    self._sync_channel_with_limit(
                        channel_semaphore, ch, sync_from, db, skip_delete=True,
                    )
                    for ch in channels_to_sync
                ],
                return_exceptions=True
            )

            total_synced = 0
            total_errors = 0
            total_skipped = 0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"[SLACK][FULL SYNC] Channel {channels_to_sync[i]['name']} failed: {result}"
                    )
                    total_errors += 1
                else:
                    total_synced += result.get("synced", 0)
                    total_errors += result.get("errors", 0)
                    if result.get("skipped"):
                        total_skipped += 1
            
            slack_sync.update_sync_progress(
                db, self.team_id, SlackEntityType.MESSAGE,
                synced_count=total_synced,
            )

            if total_skipped > 0:
                logger.info(
                    f"[SLACK][FULL SYNC] {total_synced} synced, {total_errors} errors, "
                    f"{total_skipped} channels skipped (not_in_channel/missing_scope)"
                )

            slack_sync.mark_sync_completed(
                db, self.team_id, SlackEntityType.MESSAGE, total_synced
            )
            return {"synced": total_synced, "errors": total_errors, "skipped": total_skipped}

        except Exception as e:
            logger.error(f"[SLACK][FULL SYNC] Message sync failed: {e}")
            db.rollback()
            try:
                slack_sync.create_or_update_sync_state(
                    db, self.team_id, SlackEntityType.MESSAGE,
                    SlackSyncStatus.FAILED, error=str(e)[:500]
                )
            except Exception:
                db.rollback()
            return {"synced": 0, "errors": 1}

    async def _sync_channel_with_limit(
        self,
        semaphore: asyncio.Semaphore,
        channel: dict[str, str],
        sync_from: str | None,
        db: Session | None = None,
        skip_delete: bool = False,
    ) -> dict[str, int]:
        """Semaphore 제한 하에 단일 채널 동기화 실행"""
        async with semaphore:
            return await self._sync_channel_messages(
                channel["id"], channel["name"], sync_from, db,
                skip_delete=skip_delete,
            )
            
    async def _sync_channel_messages(
        self,
        channel_id: str,
        channel_name: str,
        sync_from: str | None,
        db: Session | None = None,
        skip_delete: bool = False,
    ) -> dict[str, int]:
        """단일 채널: fetch → summarize → embed → store 4단계 파이프라인"""
        SKIPPABLE_ERRORS = {"not_in_channel", "channel_not_found", "missing_scope"}

        if db:
            slack_sync.start_channel_sync(
                db, self.team_id, channel_id,
                channel_name=channel_name,
                oldest_ts=sync_from,
            )

        fetch_q: asyncio.Queue = asyncio.Queue(maxsize=2)
        embed_q: asyncio.Queue = asyncio.Queue(maxsize=2)
        store_q: asyncio.Queue = asyncio.Queue(maxsize=2)

        async def _fetch_stage():
            async for batch in self._fetch_channel_pages(
                channel_id, channel_name, sync_from,
            ):
                await fetch_q.put(batch)
            await fetch_q.put(None)

        async def _summarize_stage():
            while (batch := await fetch_q.get()) is not None:
                batch_docs, batch_ids, batch_errors = batch
                if self.summarizer:
                    batch_docs = await self._summarize_documents(batch_docs)
                await embed_q.put((batch_docs, batch_ids, batch_errors))
            await embed_q.put(None)

        async def _embed_stage():
            while (batch := await embed_q.get()) is not None:
                batch_docs, batch_ids, batch_errors = batch
                embeddings = await self.repository.generate_embeddings(batch_docs)
                await store_q.put((batch_docs, batch_ids, batch_errors, embeddings))
            await store_q.put(None)

        async def _store_stage() -> tuple[int, int]:
            synced_count = 0
            errors = 0
            while (batch := await store_q.get()) is not None:
                batch_docs, batch_ids, batch_errors, embeddings = batch
                errors += batch_errors
                if not skip_delete:
                    await self.repository.delete_documents(batch_ids)
                await self.repository.store_with_embeddings(
                    batch_docs, embeddings, batch_ids,
                )
                synced_count += len(batch_docs)
                if db:
                    slack_sync.update_sync_progress(
                        db, self.team_id, SlackEntityType.MESSAGE,
                        synced_count=synced_count,
                    )
                    slack_sync.update_channel_sync_progress(
                        db, self.team_id, channel_id,
                        synced_count=synced_count,
                    )
            return synced_count, errors

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_fetch_stage())
                tg.create_task(_summarize_stage())
                tg.create_task(_embed_stage())
                store_task = tg.create_task(_store_stage())
            
            synced_count, errors = store_task.result()
        
        except ExceptionGroup as eg:
            for exc in eg.exceptions:
                if isinstance(exc, SlackApiError):
                    if exc.response.get("error", "") in SKIPPABLE_ERRORS:
                        logger.info(
                            f"[SLACK][SYNC] Skipping channel {channel_name} ({channel_id}): "
                            f"{exc.response.get('error')}"
                        )
                        return {"synced": 0, "errors": 0, "skipped": True}

            # 채널 동기화 실패
            if db:
                slack_sync.mark_channel_sync_failed(
                    db, self.team_id, channel_id,
                    error=str(eg.exceptions[0]),
                )
            raise eg.exceptions[0] from None

        # 채널 동기화 완료
        if db:
            slack_sync.mark_channel_sync_completed(
                db, self.team_id, channel_id,
                synced_count=synced_count,
            )

        logger.debug(
            f"[SLACK][SYNC] Channel {channel_name}: synced {synced_count}, errors {errors}"
        )
        return {"synced": synced_count, "errors": errors}


    async def _fetch_channel_pages(
        self,
        channel_id: str,
        channel_name: str,
        sync_from: str | None,
    ) -> AsyncGenerator[tuple[list[Document], list[str], int], None]:
        
        cursor = None

        while True:
            response = await self.client.get_conversation_history(
                channel=channel_id,
                oldest=sync_from,
                cursor=cursor,
                limit=settings.SLACK_MESSAGE_BATCH_SIZE,
            )

            messages = response.get("messages", [])

            # 스레드 답글 병렬 조회
            thread_messages = [
                msg for msg in messages
                if not self._should_skip_message(msg) and msg.get("reply_count", 0) > 0
            ]

            if thread_messages:
                thread_replies_list = await asyncio.gather(*[
                    self._fetch_thread_replies(channel_id, msg.get("ts"))
                    for msg in thread_messages
                ])
                reply_map = {
                    msg.get("ts"): replies
                    for msg, replies in zip(thread_messages, thread_replies_list)
                }
            else:
                reply_map = {}

            # 메시지 변환
            batch_documents = []
            batch_doc_ids = []
            errors = 0

            for msg_data in messages:
                if self._should_skip_message(msg_data):
                    continue

                try:
                    replies = reply_map.get(msg_data.get("ts"), [])
                    permalink = self._build_permalink(channel_id, msg_data.get("ts"))
                    message = self.transformer.parse_message(
                        msg_data, channel_id, channel_name, permalink, replies,
                    )
                    doc = self.transformer.transform_message(message, self.team_id)
                    batch_documents.append(doc)
                    batch_doc_ids.append(doc.id)
                except Exception as e:
                    logger.warning(
                        f"Failed to process message {msg_data.get('ts')}: {e}"
                    )
                    errors += 1

            if batch_documents:
                yield batch_documents, batch_doc_ids, errors

            # 다음 페이지 확인
            if not response.get("has_more"):
                break
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    async def _fetch_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> list[SlackThreadReply]:
        """Thread Reply 조회 → SlackThreadReply 리스트 변환"""
        replies = []
        cursor = None

        while True:
            response = await self.client.get_conversation_replies(
                channel=channel_id, ts=thread_ts, cursor=cursor,
            )
            messages = response.get("messages", [])

            # 첫 번째 메시지는 parent이므로 skip
            for msg in messages[1:]:
                if self._should_skip_message(msg):
                    continue
                replies.append(self.transformer.parse_reply(msg))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

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
