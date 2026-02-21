import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.connectors.confluence.schemas import (
    ConfluenceAttachmentResponse,
    ConfluenceBlogPostResponse,
    ConfluenceCommentResponse,
    ConfluenceLabelResponse,
    ConfluencePageResponse,
)
from catchup.connectors.confluence.transformers import ConfluenceTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.db.models import ConfluenceEntityType
from catchup.db.confluence import sync_repository as confluence_sync
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.db.confluence import domain_repository
from catchup.configs.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

class ConfluenceIngestionService:
    def __init__(
        self,
        cloud_id: str,
        access_token: str,
        site_url: str,
        repository: PGVectorRepository
    ):
        self.cloud_id = cloud_id
        self.site_url = site_url.rstrip("/")

        self.client = ConfluenceApiClient(cloud_id, access_token)
        self.transformer = ConfluenceTransformer()
        self.repository = repository

    async def initialize(self) -> None:
        logger.info(f"[CONFLUENCE][SERVICE] Initializing: cloud_id={self.cloud_id}")
        await self.repository.initialize()
        logger.info(f"[CONFLUENCE][SERVICE] Initialized Successfully: cloud_id={self.cloud_id}")

    # ================================================================
    # Full Sync
    # ================================================================
    async def full_sync(
            self,
            db: Session,
            space_keys: list[str] | None = None,
            sync_days: int | None = None,
    ) -> dict[str, Any]:
        days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
        sync_from = datetime.now(timezone.utc) - timedelta(days=days)

        logger.info(
            f"[CONFLUENCE][FULL SYNC] Started: "
            f"cloud_id={self.cloud_id}, spaces={space_keys or 'all'} since={sync_from.isoformat()}"
        )

        results: dict[str, Any] = {
            "pages": {"synced": 0, "errors": 0},
            "blogposts": {"synced": 0, "errors": 0},
        }

        try:
            space_id_map = domain_repository.get_space_id_map(
                db, self.cloud_id, space_keys,
            )
            space_name_map = domain_repository.get_space_name_map(
                db, self.cloud_id, space_keys,
            )
            if not space_id_map:
                logger.warning(f"[CONFLUENCE][FULL SYNC] No spaces found: cloud_id={self.cloud_id}")
                return results

            user_name_map = self._load_user_name_map(db)
            
            for space_key, space_id in space_id_map.items():
                page_result = await self._sync_space_pages(
                    db, space_id = space_id, space_key = space_key, since = sync_from,
                    user_name_map=user_name_map, space_name=space_name_map.get(space_key),
                )
                results["pages"]["synced"] += page_result["synced"]
                results["pages"]["errors"] += page_result["errors"]

                blog_result = await self._sync_space_blogposts(
                    db, space_id = space_id, space_key = space_key, since = sync_from,
                    user_name_map=user_name_map, space_name=space_name_map.get(space_key),
                )
                results["blogposts"]["synced"] += blog_result["synced"]
                results["blogposts"]["errors"] += blog_result["errors"]
            
            db.commit()

            logger.info(
                f"[CONFLUENCE][FULL SYNC] Completed : cloud_id = {self.cloud_id}, results = {results}"
            )
            return results

        except Exception as e:
            db.rollback()
            logger.error(f"[CONFLUENCE][FULL SYNC] Failed: cloud_id={self.cloud_id}, error={e}")
            raise
        
    # ================================================================
    # Incremental Sync
    # ================================================================
    async def incremental_sync(
            self,
            db: Session,
    ) -> dict[str, Any]:
        logger.info(
            f"[CONFLUENCE][INCREMENTAL SYNC] Started : cloud_id = {self.cloud_id}"
        )

        results: dict[str, Any] = {
            "pages": {"synced": 0, "skipped": 0, "errors": 0},
            "blogposts": {"synced": 0, "skipped": 0, "errors": 0},
        }

        try:
            synced_keys = confluence_sync.get_synced_space_keys(db, self.cloud_id)
            if not synced_keys:
                logger.info(
                    f"[CONFLUENCE][INCREMENTAL SYNC] No Synced Spaces Found : cloud_id = {self.cloud_id}"
                )
                return results
            
            space_id_map = domain_repository.get_space_id_map(
                db, self.cloud_id, synced_keys,
            )

            for space_key, space_id in space_id_map.items():
                page_result = await self._incremental_sync_pages(
                    db, space_id=space_id, space_key=space_key,
                )
                results["pages"]["synced"] += page_result["synced"]
                results["pages"]["skipped"] += page_result["skipped"]
                results["pages"]["errors"] += page_result["errors"]

                blog_result = await self._incremental_sync_blogposts(
                    db, space_id=space_id, space_key=space_key,
                )
                results["blogposts"]["synced"] += blog_result["synced"]
                results["blogposts"]["skipped"] += blog_result["skipped"]
                results["blogposts"]["errors"] += blog_result["errors"]

            db.commit()
            
            logger.info(
                f"[CONFLUENCE][INCREMENTAL SYNC] Completed "
                f"cloud_id = {self.cloud_id}, results = {results}"
            )
            return results

        except Exception as e:
            db.rollback()
            logger.error(
                f"[CONFLUENCE][INCREMENTAL SYNC] Failed: "
                f"cloud_id = {self.cloud_id}, error = {e}"
            )
            raise
        
    async def _incremental_sync_pages(
            self,
            db: Session,
            space_id: str,
            space_key: str,
    ) -> dict[str, int]:
        
        results = {"synced": 0, "skipped": 0, "errors": 0}

        sync_state = confluence_sync.get_sync_state(
            db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
        )
        if not sync_state or not sync_state.last_successful_sync_at:
            logger.info(
                f"[CONFLUENCE][INCREMENTAL SYNC] No Page Sync baseline, skipping : "
                f"space_key = {space_key}"
            )
            return results
        
        since = sync_state.last_successful_sync_at

        confluence_sync.mark_sync_started(
            db, self.cloud_id, space_key, ConfluenceEntityType.PAGE
        )
        db.commit()

        try:
            should_stop = False

            async for batch in self.client.iter_pages(
                space_id=space_id, body_format="storage",
            ):
                for raw_page in batch:
                    try:
                        page = ConfluencePageResponse.model_validate(raw_page)

                        modified_at = parse_atlassian_datetime(
                            page.version.created_at if page.version else None
                        )
                        if modified_at and modified_at < since:
                            should_stop = True
                            results["skipped"] += 1
                            continue
                        
                        documents = await self._process_page(page, space_key=space_key)

                        if documents:
                            doc_ids = [doc.id for doc in documents]
                            await self.repository.delete_by_id_prefix(
                                f"confluence:page:{page.id}:chunk"
                            )
                            await self.repository.add_documents(documents, doc_ids)
                        
                        results["synced"] += 1

                    except Exception as e:
                        logger.error(
                            f"[CONFLUENCE][INCREMENTAL SYNC] Failed to process page: "
                            f"space_key={space_key}, page_id={raw_page.get('id')}, error={e}"
                        )
                        results["errors"] += 1

                if should_stop:
                    break
                
            logger.info(
                f"[CONFLUENCE][INCREMENTAL SYNC] Pages completed: "
                f"space_key={space_key}, synced={results['synced']}, "
                f"skipped={results['skipped']}, errors={results['errors']}"
            )

            if results["errors"] == 0:
                confluence_sync.mark_sync_completed(
                    db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
                    synced_count=results["synced"],
                )
            else:
                confluence_sync.mark_sync_failed(
                    db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
                    error=f"{results['errors']} pages failed to process",
                )
            db.commit()

        except Exception as e:
            confluence_sync.mark_sync_failed(
                db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
                error=str(e),
            )
            db.commit()
            logger.error(
                f"[CONFLUENCE][INCREMENTAL SYNC] Page sync failed: "
                f"space_key={space_key}, error={e}"
            )
            results["errors"] += 1

        return results
    

    async def _incremental_sync_blogposts(
        self,
        db: Session,
        space_id: str,
        space_key: str,
    ) -> dict[str, int]:

        results = {"synced": 0, "skipped": 0, "errors": 0}

        sync_state = confluence_sync.get_sync_state(
            db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
        )
        if not sync_state or not sync_state.last_successful_sync_at:
            logger.info(
                f"[CONFLUENCE][INCREMENTAL SYNC] No blogpost sync baseline, skipping: "
                f"space_key={space_key}"
            )
            return results

        since = sync_state.last_successful_sync_at

        confluence_sync.mark_sync_started(
            db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
        )
        db.commit()

        try:
            should_stop = False

            async for batch in self.client.iter_blogposts(
                space_id=space_id, body_format="storage",
            ):
                for raw_blogpost in batch:
                    try:
                        blogpost = ConfluenceBlogPostResponse.model_validate(raw_blogpost)

                        modified_at = parse_atlassian_datetime(
                            blogpost.version.created_at if blogpost.version else None
                        )
                        if modified_at and modified_at < since:
                            should_stop = True
                            results["skipped"] += 1
                            continue

                        documents = await self._process_blogpost(
                            blogpost, space_key=space_key,
                        )

                        if documents:
                            doc_ids = [doc.id for doc in documents]
                            await self.repository.delete_by_id_prefix(
                                f"confluence:blogpost:{blogpost.id}:chunk:"
                            )
                            await self.repository.add_documents(documents, doc_ids)

                        results["synced"] += 1

                    except Exception as e:
                        logger.error(
                            f"[CONFLUENCE][INCREMENTAL SYNC] Failed to process blogpost: "
                            f"space_key={space_key}, blogpost_id={raw_blogpost.get('id')}, "
                            f"error={e}"
                        )
                        results["errors"] += 1

                if should_stop:
                    break

            logger.info(
                f"[CONFLUENCE][INCREMENTAL SYNC] Blogposts completed: "
                f"space_key={space_key}, synced={results['synced']}, "
                f"skipped={results['skipped']}, errors={results['errors']}"
            )

            if results["errors"] == 0:
                confluence_sync.mark_sync_completed(
                    db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                    synced_count=results["synced"],
                )
            else:
                confluence_sync.mark_sync_failed(
                    db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                    error=f"{results['errors']} blogposts failed to process",
                )
            db.commit()

        except Exception as e:
            confluence_sync.mark_sync_failed(
                db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                error=str(e),
            )
            db.commit()
            logger.error(
                f"[CONFLUENCE][INCREMENTAL SYNC] Blogpost sync failed: "
                f"space_key={space_key}, error={e}"
            )
            results["errors"] += 1

        return results


    async def _sync_space_pages(
            self,
            db: Session,
            space_id: str,
            space_key: str,
            since: datetime | None = None,
            user_name_map: dict[str, str | None] | None = None,
            space_name: str | None = None,
    ) -> dict[str, int]:

        results = {"synced": 0, "errors": 0}

        confluence_sync.mark_sync_started(
            db, self.cloud_id, space_key, ConfluenceEntityType.PAGE,
        )
        db.commit()

        try:
            should_stop = False
            async for batch in self.client.iter_pages(
                space_id=space_id, body_format="storage",
            ):
                for raw_page in batch:
                    try:
                        page = ConfluencePageResponse.model_validate(raw_page)

                        modified_at = parse_atlassian_datetime(
                            page.version.created_at if page.version else None
                        )
                        if since and modified_at and modified_at < since:
                            should_stop = True
                            continue

                        documents = await self._process_page(
                            page, space_key=space_key, space_name=space_name, user_name_map=user_name_map,
                        )

                        if documents:
                            doc_ids = [doc.id for doc in documents]
                            await self.repository.delete_by_id_prefix(f"confluence:page:{page.id}:chunk:")
                            await self.repository.add_documents(documents, doc_ids)

                        results["synced"] += 1

                    except Exception as e:
                        logger.error(
                            f"[CONFLUENCE][SYNC] Failed to process page: "
                            f"space_key={space_key}, page_id={raw_page.get('id')}, error={e}"
                        )
                        results["errors"] += 1
                if should_stop:
                    break

            logger.info(
                f"[CONFLUENCE][SYNC] Pages completed: "
                f"space_key={space_key}, synced={results['synced']}, errors={results['errors']}"
            )

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
            since: datetime | None = None,
            user_name_map: dict[str, str | None] | None = None,
            space_name: str | None = None,
    ) -> dict[str, int]:
        
        results = {"synced": 0, "errors": 0}

        confluence_sync.mark_sync_started(
            db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
        )
        db.commit()

        try:
            should_stop = False
            async for batch in self.client.iter_blogposts(
                space_id = space_id, body_format="storage",
            ):
                for raw_blogpost in batch:
                    try:
                        blogpost = ConfluenceBlogPostResponse.model_validate(raw_blogpost)

                        modified_at = parse_atlassian_datetime(
                            blogpost.version.created_at if blogpost.version else None
                        )
                        if since and modified_at and modified_at < since:
                            should_stop = True
                            continue

                        documents = await self._process_blogpost(
                            blogpost, space_key = space_key, space_name=space_name, user_name_map=user_name_map,
                        )

                        if documents:
                            doc_ids = [doc.id for doc in documents]
                            await self.repository.delete_by_id_prefix(f"confluence:blogpost:{blogpost.id}:chunk:")
                            await self.repository.add_documents(documents, doc_ids)
                        
                        results["synced"] += 1

                    except Exception as e:
                        logger.error(
                            f"[CONFLUENCE][SYNC] Failed to process blogpost: "
                            f"space_key = {space_key}, blogpost_id = {raw_blogpost.get('id')}, error = {e}"
                        )
                        results["errors"] += 1
                if should_stop:
                    break

            logger.info(
                f"[CONFLUENCE][SYNC] Blogposts completed: "
                f"space_key={space_key}, synced={results['synced']}, errors={results['errors']}"
            )

            confluence_sync.mark_sync_completed(
                db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                synced_count=results["synced"],
            )
            db.commit()

        except Exception as e:
            confluence_sync.mark_sync_failed(
                db, self.cloud_id, space_key, ConfluenceEntityType.BLOGPOST,
                error = str(e)
            )
            db.commit()
            logger.error(
                f"[CONFLUENCE][SYNC] Blogpost sync failed: space_key={space_key}, error={e}"
            )
            results["errors"] += 1
        
        return results
           

    async def _process_page(
            self,
            page: ConfluencePageResponse,
            space_key: str,
            space_name: str | None = None,
            user_name_map: dict[str, str | None] | None = None,
    ) -> list[Document]:
        
        footer_comments, inline_comments, labels, attachments = await self._fetch_supplementary(
            content_type="pages", content_id = page.id,
        )

        attachment_images = await self._download_images(attachments)

        return self.transformer.transform_page(
            page,
            space_key = space_key,
            space_name = space_name,
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=inline_comments,
            attachment_images=attachment_images,
            site_url = self.site_url,
            user_name_map=user_name_map,
        )
    
    async def _process_blogpost(
        self,
        blogpost: ConfluenceBlogPostResponse,
        space_key: str,
        space_name: str | None = None,
        user_name_map: dict[str, str | None] | None = None,
    ) -> list[Document]:

        footer_comments, _, labels, attachments = await self._fetch_supplementary(
            content_type="blogposts", content_id=blogpost.id,
        )

        attachment_images = await self._download_images(attachments)

        return self.transformer.transform_blogpost(
            blogpost,
            space_key=space_key,
            space_name=space_name,
            labels=labels,
            footer_comments=footer_comments,
            attachment_images=attachment_images,
            site_url=self.site_url,
            user_name_map=user_name_map,
        )
    
    def _load_user_name_map(self, db: Session) -> dict[str, str | None]:
        """
        ConfluenceUsers 테이블에서 account_type이 'atlassian'인 사용자만 로드해
        account_id → display_name 매핑을 만든다. Full Sync에서 작성자 이름 주입용으로 사용.
        """
        users = domain_repository.get_users_by_cloud_id(db, self.cloud_id)
        mapping = {
            user.account_id: (user.display_name or user.public_name)
            for user in users
            if user.account_type == "atlassian"
        }
        logger.info(
            f"[CONFLUENCE][USER CACHE] Loaded {len(mapping)} atlassian users for cloud_id={self.cloud_id}"
        )
        return mapping

    async def _fetch_supplementary(
            self,
            content_type: str,
            content_id: str,
    ) -> tuple[
        list[ConfluenceCommentResponse],        # footer_comments
        list[ConfluenceCommentResponse],        # inline_comments
        list[str],                              # labels
        list[ConfluenceAttachmentResponse],     # attachments
    ]:
        tasks = [
            self.client.get_content_footer_comments(content_type, content_id),
            self.client.get_content_attachments(content_type, content_id),
            self.client.get_content_labels(content_type, content_id),
        ]

        if content_type == "pages":
            tasks.append(self.client.get_content_inline_comments(content_type, content_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        footer_comments = []
        if isinstance(results[0], list):
            footer_comments = [ConfluenceCommentResponse.model_validate(r) for r in results[0]]

        attachments = []
        if isinstance(results[1], list):
            attachments = [ConfluenceAttachmentResponse.model_validate(r) for r in results[1]]

        labels = []
        if isinstance(results[2], list):
            labels = [ConfluenceLabelResponse.model_validate(r).name for r in results[2]]

        inline_comments = []
        if content_type == "pages" and len(results) > 3 and isinstance(results[3], list):
            inline_comments = [ConfluenceCommentResponse.model_validate(r) for r in results[3]]
        
        return footer_comments, inline_comments, labels, attachments
    
    async def _download_images(
            self,
            attachments: list[ConfluenceAttachmentResponse]
    ) -> dict[str, bytes]:
        image_attachments = [
            att for att in attachments
            if att.media_type in SUPPORTED_IMAGE_TYPES
        ]

        if not image_attachments:
            return {}
        
        results: dict[str, bytes] = {}

        for att in image_attachments:
            data = await self.client.download_attachment(att.id)
            if data:
                results[att.title] = data
        
        return results
