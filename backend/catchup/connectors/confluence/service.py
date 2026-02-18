"""
Confluence 데이터 동기화 서비스

Confluence API에서 Page/BlogPost를 가져와 PGVector에 저장하는 서비스.
ConfluenceApiClient, ConfluenceTransformer, PGVectorRepository를 조합.

사용법:
    service = ConfluenceIngestionService(cloud_id, access_token, site_url)
    await service.initialize()

    # 전체 동기화
    await service.full_sync(db, space_keys=["ENG", "DEV"])

    # 증분 동기화
    await service.incremental_sync(db)
"""

import asyncio
import logging
from typing import Any

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.connectors.confluence.client import (
    ConfluenceApiClient,
    ConfluenceApiError,
    ConfluenceRateLimitError,
)
from catchup.connectors.confluence.schemas import (
    ConfluenceAttachmentResponse,
    ConfluenceBlogPostResponse,
    ConfluenceCommentResponse,
    ConfluenceLabelResponse,
    ConfluencePageResponse,
    ConfluenceSpaceResponse,
)
from catchup.connectors.confluence.transformers import ConfluenceTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.db.models import ConfluenceEntityType
from catchup.db.confluence import domain_repository as confluence_entities
from catchup.db.confluence import sync_repository as confluence_sync

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class ConfluenceIngestionService:
    """
    Confluence 데이터 동기화 서비스

    Confluence Cloud에서 Page/BlogPost를 가져와
    PGVector 벡터 저장소에 적재.
    """

    def __init__(
        self,
        cloud_id: str,
        access_token: str,
        site_url: str,
    ):
        self.cloud_id = cloud_id
        self.site_url = site_url.rstrip("/")

        self.client = ConfluenceApiClient(cloud_id, access_token)
        self.transformer = ConfluenceTransformer()
        self.repository = PGVectorRepository()

        self._initialized = False

    async def initialize(self) -> None:
        """PGVector 초기화"""
        if self._initialized:
            return

        logger.info(f"[CONFLUENCE][SERVICE] Initializing: cloud_id={self.cloud_id}")

        await self.repository.initialize()

        self._initialized = True
        logger.info("[CONFLUENCE][SERVICE] Initialized successfully")

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError(
                "ConfluenceIngestionService not initialized. "
                "Call await service.initialize() first."
            )

    # ================================================================
    # Full Sync
    # ================================================================

    async def full_sync(
        self,
        db: Session,
        space_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        전체 동기화

        Space 목록 조회 → Space별 Page + BlogPost 동기화

        Args:
            db: SQLAlchemy Session
            space_keys: 동기화 대상 Space Key 목록 (None이면 전체)

        Returns:
            {"pages": {"synced": N, "errors": M}, "blogposts": {"synced": N, "errors": M}}
        """
        self._ensure_initialized()

        logger.info(
            f"[CONFLUENCE][FULL SYNC] Started: "
            f"cloud_id={self.cloud_id}, spaces={space_keys or 'all'}"
        )

        results: dict[str, Any] = {
            "pages": {"synced": 0, "errors": 0},
            "blogposts": {"synced": 0, "errors": 0},
        }

        try:
            spaces = await self._resolve_spaces(db, space_keys)
            if not spaces:
                logger.warning(f"[CONFLUENCE][FULL SYNC] No spaces found: cloud_id={self.cloud_id}")
                return results

            for space in spaces:
                space_key = space.key
                space_name = space.name
                space_id = space.id

                # Pages
                page_result = await self._sync_space_pages(
                    db, space_id=space_id, space_key=space_key, space_name=space_name,
                )
                results["pages"]["synced"] += page_result["synced"]
                results["pages"]["errors"] += page_result["errors"]

                # BlogPosts
                blog_result = await self._sync_space_blogposts(
                    db, space_id=space_id, space_key=space_key, space_name=space_name,
                )
                results["blogposts"]["synced"] += blog_result["synced"]
                results["blogposts"]["errors"] += blog_result["errors"]

            db.commit()

            logger.info(
                f"[CONFLUENCE][FULL SYNC] Completed: cloud_id={self.cloud_id}, results={results}"
            )
            return results

        except Exception as e:
            db.rollback()
            logger.error(f"[CONFLUENCE][FULL SYNC] Failed: cloud_id={self.cloud_id}, error={e}")
            raise

    async def _resolve_spaces(
        self,
        db: Session,
        space_keys: list[str] | None,
    ) -> list[ConfluenceSpaceResponse]:
        """
        동기화 대상 Space 목록 결정

        space_keys가 지정되면 해당 Space만, 아니면 API에서 전체 조회.
        """
        raw_spaces = await self.client.get_spaces(status="current")
        spaces = [ConfluenceSpaceResponse.model_validate(s) for s in raw_spaces]

        if space_keys:
            target_keys = set(space_keys)
            spaces = [s for s in spaces if s.key in target_keys]

        logger.info(
            f"[CONFLUENCE][SERVICE] Resolved {len(spaces)} spaces: "
            f"cloud_id={self.cloud_id}"
        )
        return spaces

    async def _sync_space_pages(
        self,
        db: Session,
        space_id: str,
        space_key: str,
        space_name: str,
    ) -> dict[str, int]:
        """
        Space 내 Page 전체 동기화

        1. get_pages(space_id, body_format=storage) → 페이지 목록
        2. 페이지별: comments, labels, attachments 조회
        3. 이미지 attachment → download_attachment() → bytes
        4. transformer.transform_page() → list[Document]
        5. repository.upsert_documents()
        6. SyncState 업데이트
        """
        results = {"synced": 0, "errors": 0}

        confluence_sync.mark_sync_started(
            db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
        )
        db.commit()

        try:
            raw_pages = await self.client.get_pages(
                space_id=space_id,
                body_format="storage",
            )

            logger.info(
                f"[CONFLUENCE][SYNC] Fetched {len(raw_pages)} pages: "
                f"space_key={space_key}"
            )

            for raw_page in raw_pages:
                try:
                    page = ConfluencePageResponse.model_validate(raw_page)
                    documents = await self._process_page(
                        page, space_key=space_key, space_name=space_name,
                    )

                    if documents:
                        doc_ids = [doc.id for doc in documents]
                        # Delete-then-Insert: 기존 chunk 삭제 후 새 chunk 저장
                        existing_ids = self._build_existing_chunk_ids(
                            entity_type="page", content_id=page.id, max_chunks=100,
                        )
                        await self.repository.delete_documents(existing_ids)
                        await self.repository.upsert_documents(documents, doc_ids)
                        results["synced"] += 1
                    else:
                        results["synced"] += 1  # 빈 body도 성공 처리

                except Exception as e:
                    logger.error(
                        f"[CONFLUENCE][SYNC] Failed to process page: "
                        f"space_key={space_key}, page_id={raw_page.get('id')}, error={e}"
                    )
                    results["errors"] += 1

            confluence_sync.mark_sync_completed(
                db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
                synced_count=results["synced"],
            )
            db.commit()

        except Exception as e:
            confluence_sync.mark_sync_failed(
                db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
                error=str(e),
            )
            db.commit()
            logger.error(
                f"[CONFLUENCE][SYNC] Page sync failed: space_key={space_key}, error={e}"
            )
            results["errors"] += 1

        return results

    async def _sync_space_blogposts(
        self,
        db: Session,
        space_id: str,
        space_key: str,
        space_name: str,
    ) -> dict[str, int]:
        """Space 내 BlogPost 전체 동기화 (_sync_space_pages와 동일 구조)"""
        results = {"synced": 0, "errors": 0}

        confluence_sync.mark_sync_started(
            db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
        )
        db.commit()

        try:
            raw_blogposts = await self.client.get_blogposts(
                space_id=space_id,
                body_format="storage",
            )

            logger.info(
                f"[CONFLUENCE][SYNC] Fetched {len(raw_blogposts)} blogposts: "
                f"space_key={space_key}"
            )

            for raw_blogpost in raw_blogposts:
                try:
                    blogpost = ConfluenceBlogPostResponse.model_validate(raw_blogpost)
                    documents = await self._process_blogpost(
                        blogpost, space_key=space_key, space_name=space_name,
                    )

                    if documents:
                        doc_ids = [doc.id for doc in documents]
                        existing_ids = self._build_existing_chunk_ids(
                            entity_type="blogpost", content_id=blogpost.id, max_chunks=100,
                        )
                        await self.repository.delete_documents(existing_ids)
                        await self.repository.upsert_documents(documents, doc_ids)
                        results["synced"] += 1
                    else:
                        results["synced"] += 1

                except Exception as e:
                    logger.error(
                        f"[CONFLUENCE][SYNC] Failed to process blogpost: "
                        f"space_key={space_key}, blogpost_id={raw_blogpost.get('id')}, error={e}"
                    )
                    results["errors"] += 1

            confluence_sync.mark_sync_completed(
                db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                synced_count=results["synced"],
            )
            db.commit()

        except Exception as e:
            confluence_sync.mark_sync_failed(
                db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                error=str(e),
            )
            db.commit()
            logger.error(
                f"[CONFLUENCE][SYNC] BlogPost sync failed: space_key={space_key}, error={e}"
            )
            results["errors"] += 1

        return results

    # ================================================================
    # Content Processing (Page / BlogPost 공통)
    # ================================================================

    async def _process_page(
        self,
        page: ConfluencePageResponse,
        space_key: str,
        space_name: str,
    ) -> list[Document]:
        """
        단일 Page 처리: comments, labels, attachments 조회 → transform → Document 리스트
        """
        page_id = page.id

        # 병렬로 부가 데이터 조회
        footer_comments, inline_comments, labels, attachment_images = (
            await self._fetch_page_supplementary(page_id)
        )

        documents = self.transformer.transform_page(
            page,
            space_key=space_key,
            space_name=space_name,
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=inline_comments,
            attachment_images=attachment_images,
            site_url=self.site_url,
        )

        return documents

    async def _process_blogpost(
        self,
        blogpost: ConfluenceBlogPostResponse,
        space_key: str,
        space_name: str,
    ) -> list[Document]:
        """단일 BlogPost 처리"""
        page_id = blogpost.id

        # BlogPost는 inline comment 없음
        footer_raw, labels_raw, attachments_raw = await asyncio.gather(
            self._safe_api_call(self.client.get_page_footer_comments, page_id, body_format="storage"),
            self._safe_api_call(self.client.get_page_labels, page_id),
            self._safe_api_call(self.client.get_page_attachments, page_id),
        )

        footer_comments = self._parse_comments(footer_raw)
        labels = self._parse_labels(labels_raw)
        attachment_images = await self._download_images(attachments_raw)

        documents = self.transformer.transform_blogpost(
            blogpost,
            space_key=space_key,
            space_name=space_name,
            labels=labels,
            footer_comments=footer_comments,
            attachment_images=attachment_images,
            site_url=self.site_url,
        )

        return documents

    async def _fetch_page_supplementary(
        self,
        page_id: str,
    ) -> tuple[
        list[ConfluenceCommentResponse],
        list[ConfluenceCommentResponse],
        list[str],
        dict[str, bytes],
    ]:
        """Page의 부가 데이터 병렬 조회 (footer/inline comments, labels, attachments)"""
        footer_raw, inline_raw, labels_raw, attachments_raw = await asyncio.gather(
            self._safe_api_call(self.client.get_page_footer_comments, page_id, body_format="storage"),
            self._safe_api_call(self.client.get_page_inline_comments, page_id, body_format="storage"),
            self._safe_api_call(self.client.get_page_labels, page_id),
            self._safe_api_call(self.client.get_page_attachments, page_id),
        )

        footer_comments = self._parse_comments(footer_raw)
        inline_comments = self._parse_comments(inline_raw)
        labels = self._parse_labels(labels_raw)
        attachment_images = await self._download_images(attachments_raw)

        return footer_comments, inline_comments, labels, attachment_images

    # ================================================================
    # Incremental Sync
    # ================================================================

    async def incremental_sync(
        self,
        db: Session,
        space_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        증분 동기화

        last_successful_sync_at 이후 변경된 Page/BlogPost만 처리.
        CQL: lastModified >= "YYYY-MM-DD" 사용.

        이전 sync 이력이 없으면 full_sync로 폴백.
        """
        self._ensure_initialized()

        logger.info(
            f"[CONFLUENCE][INCREMENTAL SYNC] Started: "
            f"cloud_id={self.cloud_id}, spaces={space_keys or 'all'}"
        )

        results: dict[str, Any] = {
            "pages": {"synced": 0, "errors": 0},
            "blogposts": {"synced": 0, "errors": 0},
        }

        try:
            spaces = await self._resolve_spaces(db, space_keys)
            if not spaces:
                return results

            has_any_sync_history = False
            all_sync_states = confluence_sync.get_all_sync_states(db, self.cloud_id)
            if all_sync_states:
                has_any_sync_history = any(
                    s.last_successful_sync_at for s in all_sync_states
                )

            if not has_any_sync_history:
                logger.info(
                    f"[CONFLUENCE][INCREMENTAL SYNC] No sync history, falling back to full_sync: "
                    f"cloud_id={self.cloud_id}"
                )
                return await self.full_sync(db, space_keys=space_keys)

            for space in spaces:
                space_key = space.key
                space_name = space.name
                space_id = space.id

                # Page incremental
                page_state = confluence_sync.get_sync_state(
                    db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
                )
                if page_state and page_state.last_successful_sync_at:
                    since_str = page_state.last_successful_sync_at.strftime("%Y-%m-%d")
                    page_result = await self._incremental_sync_pages(
                        db, space_id=space_id, space_key=space_key,
                        space_name=space_name, since=since_str,
                    )
                else:
                    # 해당 Space의 Page sync 이력 없음 → Space 단위 full sync
                    page_result = await self._sync_space_pages(
                        db, space_id=space_id, space_key=space_key, space_name=space_name,
                    )
                results["pages"]["synced"] += page_result["synced"]
                results["pages"]["errors"] += page_result["errors"]

                # BlogPost incremental
                blog_state = confluence_sync.get_sync_state(
                    db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                )
                if blog_state and blog_state.last_successful_sync_at:
                    since_str = blog_state.last_successful_sync_at.strftime("%Y-%m-%d")
                    blog_result = await self._incremental_sync_blogposts(
                        db, space_id=space_id, space_key=space_key,
                        space_name=space_name, since=since_str,
                    )
                else:
                    blog_result = await self._sync_space_blogposts(
                        db, space_id=space_id, space_key=space_key, space_name=space_name,
                    )
                results["blogposts"]["synced"] += blog_result["synced"]
                results["blogposts"]["errors"] += blog_result["errors"]

            db.commit()

            logger.info(
                f"[CONFLUENCE][INCREMENTAL SYNC] Completed: "
                f"cloud_id={self.cloud_id}, results={results}"
            )
            return results

        except Exception as e:
            db.rollback()
            logger.error(
                f"[CONFLUENCE][INCREMENTAL SYNC] Failed: "
                f"cloud_id={self.cloud_id}, error={e}"
            )
            raise

    async def _incremental_sync_pages(
        self,
        db: Session,
        space_id: str,
        space_key: str,
        space_name: str,
        since: str,
    ) -> dict[str, int]:
        """CQL로 변경된 Page만 조회하여 동기화"""
        results = {"synced": 0, "errors": 0}

        confluence_sync.mark_sync_started(
            db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
        )
        db.commit()

        try:
            # v2 API는 CQL 미지원이므로, 전체 조회 후 클라이언트 사이드 필터링
            raw_pages = await self.client.get_pages(
                space_id=space_id,
                body_format="storage",
                sort="-modified-date",
            )

            # 클라이언트 사이드 날짜 필터링
            filtered_pages = []
            for raw_page in raw_pages:
                version = raw_page.get("version", {})
                modified_at = version.get("createdAt", "")
                if modified_at >= since:
                    filtered_pages.append(raw_page)

            logger.info(
                f"[CONFLUENCE][INCREMENTAL] Filtered {len(filtered_pages)}/{len(raw_pages)} pages "
                f"modified since {since}: space_key={space_key}"
            )

            for raw_page in filtered_pages:
                try:
                    page = ConfluencePageResponse.model_validate(raw_page)
                    documents = await self._process_page(
                        page, space_key=space_key, space_name=space_name,
                    )

                    if documents:
                        doc_ids = [doc.id for doc in documents]
                        existing_ids = self._build_existing_chunk_ids(
                            entity_type="page", content_id=page.id, max_chunks=100,
                        )
                        await self.repository.delete_documents(existing_ids)
                        await self.repository.upsert_documents(documents, doc_ids)
                    results["synced"] += 1

                except Exception as e:
                    logger.error(
                        f"[CONFLUENCE][INCREMENTAL] Failed page: "
                        f"page_id={raw_page.get('id')}, error={e}"
                    )
                    results["errors"] += 1

            confluence_sync.mark_sync_completed(
                db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
                synced_count=results["synced"],
            )
            db.commit()

        except Exception as e:
            confluence_sync.mark_sync_failed(
                db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
                error=str(e),
            )
            db.commit()
            results["errors"] += 1

        return results

    async def _incremental_sync_blogposts(
        self,
        db: Session,
        space_id: str,
        space_key: str,
        space_name: str,
        since: str,
    ) -> dict[str, int]:
        """CQL로 변경된 BlogPost만 조회하여 동기화"""
        results = {"synced": 0, "errors": 0}

        confluence_sync.mark_sync_started(
            db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
        )
        db.commit()

        try:
            raw_blogposts = await self.client.get_blogposts(
                space_id=space_id,
                body_format="storage",
                sort="-modified-date",
            )

            filtered_blogposts = []
            for raw_bp in raw_blogposts:
                version = raw_bp.get("version", {})
                modified_at = version.get("createdAt", "")
                if modified_at >= since:
                    filtered_blogposts.append(raw_bp)

            logger.info(
                f"[CONFLUENCE][INCREMENTAL] Filtered {len(filtered_blogposts)}/{len(raw_blogposts)} "
                f"blogposts modified since {since}: space_key={space_key}"
            )

            for raw_bp in filtered_blogposts:
                try:
                    blogpost = ConfluenceBlogPostResponse.model_validate(raw_bp)
                    documents = await self._process_blogpost(
                        blogpost, space_key=space_key, space_name=space_name,
                    )

                    if documents:
                        doc_ids = [doc.id for doc in documents]
                        existing_ids = self._build_existing_chunk_ids(
                            entity_type="blogpost", content_id=blogpost.id, max_chunks=100,
                        )
                        await self.repository.delete_documents(existing_ids)
                        await self.repository.upsert_documents(documents, doc_ids)
                    results["synced"] += 1

                except Exception as e:
                    logger.error(
                        f"[CONFLUENCE][INCREMENTAL] Failed blogpost: "
                        f"blogpost_id={raw_bp.get('id')}, error={e}"
                    )
                    results["errors"] += 1

            confluence_sync.mark_sync_completed(
                db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                synced_count=results["synced"],
            )
            db.commit()

        except Exception as e:
            confluence_sync.mark_sync_failed(
                db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                error=str(e),
            )
            db.commit()
            results["errors"] += 1

        return results

    # ================================================================
    # Document 삭제 (Webhook 삭제 이벤트용)
    # ================================================================

    async def delete_page_documents(
        self,
        page_ids: list[str],
        entity_type: str = "page",
    ) -> int:
        """
        Page/BlogPost의 모든 chunk Document 삭제

        Webhook의 page_trashed/page_removed 이벤트에서 호출.
        """
        self._ensure_initialized()

        unique_ids = sorted({pid for pid in page_ids if pid})
        if not unique_ids:
            return 0

        all_doc_ids: list[str] = []
        for page_id in unique_ids:
            chunk_ids = self._build_existing_chunk_ids(
                entity_type=entity_type, content_id=page_id, max_chunks=100,
            )
            all_doc_ids.extend(chunk_ids)

        if all_doc_ids:
            await self.repository.delete_documents(all_doc_ids)

        logger.info(
            f"[CONFLUENCE][DELETE] Deleted documents: "
            f"cloud_id={self.cloud_id}, entity_type={entity_type}, "
            f"page_count={len(unique_ids)}, doc_count={len(all_doc_ids)}"
        )
        return len(all_doc_ids)

    # ================================================================
    # Helper Methods
    # ================================================================

    async def _safe_api_call(self, func, *args, **kwargs) -> list:
        """API 호출 실패 시 빈 리스트 반환"""
        try:
            return await func(*args, **kwargs)
        except ConfluenceRateLimitError:
            raise  # Rate limit는 상위로 전파
        except ConfluenceApiError as e:
            logger.warning(
                f"[CONFLUENCE][SERVICE] API call failed (non-critical): "
                f"func={func.__name__}, error={e}"
            )
            return []

    def _parse_comments(
        self, raw_comments: list[dict],
    ) -> list[ConfluenceCommentResponse]:
        """raw dict → ConfluenceCommentResponse 리스트"""
        comments = []
        for raw in raw_comments:
            try:
                comments.append(ConfluenceCommentResponse.model_validate(raw))
            except Exception as e:
                logger.warning(f"[CONFLUENCE][SERVICE] Failed to parse comment: {e}")
        return comments

    def _parse_labels(self, raw_labels: list[dict]) -> list[str]:
        """raw dict → label name 리스트"""
        labels = []
        for raw in raw_labels:
            try:
                label = ConfluenceLabelResponse.model_validate(raw)
                labels.append(label.name)
            except Exception:
                pass
        return labels

    async def _download_images(
        self, raw_attachments: list[dict],
    ) -> dict[str, bytes]:
        """이미지 첨부파일 다운로드 (Cohere Embed v4용)"""
        images: dict[str, bytes] = {}

        for raw in raw_attachments:
            try:
                attachment = ConfluenceAttachmentResponse.model_validate(raw)
            except Exception:
                continue

            if not attachment.media_type or attachment.media_type not in SUPPORTED_IMAGE_TYPES:
                continue

            data = await self.client.download_attachment(attachment.id)
            if data:
                images[attachment.title] = data

        return images

    def _build_existing_chunk_ids(
        self,
        entity_type: str,
        content_id: str,
        max_chunks: int = 100,
    ) -> list[str]:
        """
        Delete-then-Insert 패턴을 위한 기존 chunk ID 목록 생성

        1 Page = N Chunks이므로 기존 chunk를 먼저 삭제해야 한다.
        실제 chunk 수를 모르므로 max_chunks까지 ID를 생성하여 삭제를 시도.
        존재하지 않는 ID 삭제는 무시된다.
        """
        return [
            f"confluence:{entity_type}:{content_id}:chunk:{i}"
            for i in range(max_chunks)
        ]
