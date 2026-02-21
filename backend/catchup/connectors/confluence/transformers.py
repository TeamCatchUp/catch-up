"""
Confluence Entity -> LangChain Document

page.body.value (Storage Format HTML)
→ ConfluenceStorageParser.parse() → Section 트리
→ ConfluenceChunker.chunk() → Chunk 리스트
→ Comment Injection
    - Inline Comment → selection 텍스트 매칭으로 해당 Chunk에 삽입
    - 매칭 실패한 Inline + Footer Comment → 별도 Discussion Chunk
→ 이미지 base64 변환 (Cohere Embed v4용)
→ LangChain Document 리스트

- confluence:page:{page_id}:chunk:{chunk_index}
- confluence:blogpost:{page_id}:chunk:{chunk_index}
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup
from langchain_core.documents import Document

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.confluence.chunker import Chunk, ConfluenceChunker
from catchup.connectors.confluence.schemas import (
    ConfluenceBlogPostResponse,
    ConfluenceCommentResponse,
    ConfluencePageResponse,
)
from catchup.connectors.confluence.storage_parser import ConfluenceStorageParser

logger = logging.getLogger(__name__)

class ConfluenceTransformer:
    def __init__(self):
        self.parser = ConfluenceStorageParser()
        self.chunker = ConfluenceChunker()

    
    def transform_page(
            self,
            page: ConfluencePageResponse,
            *,
            space_key: str | None = None,
            space_name: str | None = None,
            labels: list[str] | None = None,
            footer_comments: list[ConfluenceCommentResponse] | None = None,
            inline_comments: list[ConfluenceCommentResponse] | None = None,
            attachment_images: dict[str, bytes] | None = None,
            site_url: str | None = None,
    ) -> list[Document]:
        return self._transform_content(
            content_id=page.id,
            entity_type="page",
            status=page.status,
            title=page.title,
            body=page.body,
            space_id=page.space_id,
            space_key=space_key,
            space_name=space_name,
            parent_page_id=page.parent_id,
            author_id=page.author_id,
            created_at=page.created_at,
            version=page.version,
            web_url=page.get_web_url(),
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=inline_comments,
            attachment_images=attachment_images,
            site_url=site_url,
        )

    def transform_blogpost(
        self,
        blogpost: ConfluenceBlogPostResponse,
        *,
        space_key: str | None = None,
        space_name: str | None = None,
        labels: list[str] | None = None,
        footer_comments: list[ConfluenceCommentResponse] | None = None,
        attachment_images: dict[str, bytes] | None = None,
        site_url: str | None = None,
    ) -> list[Document]:
        return self._transform_content(
            content_id=blogpost.id,
            entity_type="blogpost",
            status=blogpost.status,
            title=blogpost.title,
            body=blogpost.body,
            space_id=blogpost.space_id,
            space_key=space_key,
            space_name=space_name,
            parent_page_id=None,
            author_id=blogpost.author_id,
            created_at=blogpost.created_at,
            version=blogpost.version,
            web_url=blogpost.get_web_url(),
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=None,
            attachment_images=attachment_images,
            site_url=site_url,
        )
    
    def _transform_content(
        self,
        content_id: str,
        entity_type: str,
        status: str,
        title: str,
        body,
        space_id: str | None,
        space_key: str | None,
        space_name: str | None,
        parent_page_id: str | None,
        author_id: str | None,
        created_at: str | None,
        version,
        web_url: str | None,
        labels: list[str] | None,
        footer_comments: list[ConfluenceCommentResponse] | None,
        inline_comments: list[ConfluenceCommentResponse] | None,
        attachment_images: dict[str, bytes] | None,
        site_url: str | None = None,
    ) -> list[Document]:
        
        labels = labels or []
        attachment_images = attachment_images or {}

        # 1) Storage HTML 추출
        storage_html = body.value if body else ""
        if not storage_html:
            logger.info(
                f"[CONFLUENCE[TRANSFORMER] Empty Body for {entity_type} {content_id}"
            )
            return []
        
        web_url = self._absolutize_web_url(web_url, site_url)

        # 2) Storage -> Section Tree
        sections = self.parser.parse(storage_html)
        if not sections:
            logger.info(
                f"[CONFLUENCE][TRANSFORM] No sections parsed for {entity_type} {content_id}"
            )
            return []
        
        # 3) Section 트리 → Chunk 리스트
        chunks = self.chunker.chunk(sections, page_title=title)
        if not chunks:
            return []

        # 4) Comment Injection
        #    - Inline: selection 매칭 성공 → 해당 chunk에 삽입
        #    - 매칭 실패 Inline + Footer → 별도 Discussion Chunk
        unmatched_inline: list[ConfluenceCommentResponse] = []
        if inline_comments:
            unmatched_inline = self._inject_inline_comments(chunks, inline_comments)

        discussion_chunk = self._build_discussion_chunk(
            chunks=chunks,
            page_title=title,
            footer_comments=footer_comments or [],
            unmatched_inline=unmatched_inline,
        )
        if discussion_chunk:
            chunks.append(discussion_chunk)

        # 5. Chunk → LangChain Document 변환
        documents: list[Document] = []
        total_chunks = len(chunks)

        # 버전 정보 추출
        updated_at = version.created_at if version else None
        version_number = version.number if version else None

        for chunk in chunks:
            # semantic_content: 임베딩용 (chunk content 그대로)
            semantic_content = chunk.content

            # contextual_content: LLM 답변 생성용 (chunk별 section 반영)
            contextual_content = self._build_contextual_content(
                title=title,
                space_name=space_name,
                labels=labels,
                author_id=author_id,
                updated_at=updated_at,
                section_hierarchy=chunk.section_hierarchy,
                chunk_body=chunk.content,
            )

            # 이미지 정보
            has_images = bool(chunk.image_blocks)
            image_urls = self._build_image_urls(
                image_blocks=chunk.image_blocks,
                site_url=site_url,
                content_id=content_id,
            )

            # Document ID: confluence:{entity_type}:{id}:chunk:{index}
            doc_id = f"confluence:{entity_type}:{content_id}:chunk:{chunk.index}"

            metadata = {
                # 소스 식별
                "source": "confluence",
                "entity_type": entity_type,
                "status": status,

                # 페이지 정보
                "id": content_id,
                "title": title,
                "url": web_url,
                "space_id": space_id,
                "space_key": space_key,
                "space_name": space_name,
                "parent_page_id": parent_page_id,

                # 작성자/시간
                "author_id": author_id,
                "created_at": created_at,
                "updated_at": updated_at,
                "version": version_number,

                # 분류
                "labels": labels,

                # Chunk 정보
                "chunk_index": chunk.index,
                "total_chunks": total_chunks,
                "section_hierarchy": chunk.section_hierarchy,

                # 이미지
                "has_images": has_images,
                "image_urls": image_urls,

                # LLM 답변 생성용
                "contextual_content": contextual_content,

                # 동기화
                "synced_at": datetime.utcnow().isoformat(),
            }

            documents.append(Document(
                page_content=semantic_content,
                metadata=metadata,
                id=doc_id,
            ))

        logger.info(
            f"[CONFLUENCE][TRANSFORM] {entity_type} '{title}' → {len(documents)} chunks"
        )

        return documents
    
    def _inject_inline_comments(
            self,
            chunks: list[Chunk],
            inline_comments: list[ConfluenceCommentResponse],
    ) -> list[ConfluenceCommentResponse]:
        
        unmatched: list[ConfluenceCommentResponse] = []

        if not chunks:
            return inline_comments
        
        ref_to_chunk: dict[str, Chunk] = {}
        for chunk in chunks:
            for ref in chunk.inline_comment_refs:
                ref_to_chunk[ref] = chunk
        
        for comment in inline_comments:
            comment_text = self._extract_comment_text(comment)
            if not comment_text:
                continue

            formatted = f"(Comment : {comment_text})"
            
            # 1) marker-ref 기반 Injection
            marker_ref = self._extract_inline_marker_ref(comment)
            target_chunk = ref_to_chunk.get(marker_ref) if marker_ref else None

            # 2) selection 텍스트 매칭
            if target_chunk is None:
                selection = self._extract_inline_selection(comment)
                if selection:
                    for chunk in chunks:
                        if selection in chunk.content:
                            target_chunk = chunk
                            break
                        
            if target_chunk is not None:
                target_chunk.content = f"{target_chunk.content}\n{formatted}"
            else:
                unmatched.append(comment)

        return unmatched


    def _build_discussion_chunk(
        self,
        chunks: list[Chunk],
        page_title: str,
        footer_comments: list[ConfluenceCommentResponse],
        unmatched_inline: list[ConfluenceCommentResponse],
    ) -> Chunk | None:
        """
        Footer Comment + 매칭 실패 Inline Comment → 별도 Discussion Chunk 생성

        Returns:
            Discussion Chunk 또는 None (댓글이 없을 때)
        """
        comment_lines: list[str] = []

        # 1) 매칭 실패 Inline Comments
        for comment in (unmatched_inline or []):
            comment_text = self._extract_comment_text(comment)
            if comment_text:
                comment_lines.append(f"Comment: {comment_text}")

        # 2) Footer Comments
        for comment in (footer_comments or []):
            comment_text = self._extract_comment_text(comment)
            if comment_text:
                comment_lines.append(f"Commented: {comment_text}")

        if not comment_lines:
            return None

        # Discussion Chunk의 index = 기존 chunks의 다음 번호
        next_index = chunks[-1].index + 1 if chunks else 0

        # Context Prefix + Discussion 본문
        prefix = f"[Page: {page_title}]\n[Section: Discussion]"
        body = "\n".join(comment_lines)
        content = f"{prefix}\n\n{body}"

        return Chunk(
            index=next_index,
            content=content,
            section_hierarchy=["Discussion"],
            char_count=len(content),
            estimated_tokens=len(content) // 4,
            image_blocks=[],
        )

    def _extract_comment_text(self, comment: ConfluenceCommentResponse) -> str:
        """
        Comment body에서 텍스트 추출

        Comment의 body도 Storage Format(XHTML)이므로
        BeautifulSoup으로 태그를 제거하고 텍스트만 추출한다.
        (Comment는 짧으므로 chunking 없이 단순 텍스트 추출)
        """
        if not comment.body or not comment.body.value:
            return ""

        value = comment.body.value

        # 이미 plain text인 경우
        if comment.body.representation == "plain":
            return value.strip()

        # Storage Format → 텍스트 추출 (태그 제거)
        soup = BeautifulSoup(value, "lxml")
        return soup.get_text(strip=True)

    def _extract_inline_selection(
        self, comment: ConfluenceCommentResponse
    ) -> str | None:
        """
        Inline Comment의 selection(선택된 텍스트) 추출

        Confluence Inline Comment API는 properties 필드에
        해당 댓글이 달린 원문 텍스트(selection)를 저장한다.

        properties 구조 예시:
        {
            "inline-marker-ref": "...",
            "inline-original-selection": "선택된 원문 텍스트"
        }
        """
        if not comment.properties:
            return None

        # inline-original-selection 키에서 선택 텍스트 추출
        selection = comment.properties.get("inline-original-selection")
        if isinstance(selection, str):
            return selection.strip() if selection.strip() else None

        # nested dict 형태일 수도 있음
        if isinstance(selection, dict):
            value = selection.get("value")
            if isinstance(value, str):
                return value.strip() if value.strip() else None

        return None
    
    def _extract_inline_marker_ref(
            self, comment: ConfluenceCommentResponse
    ) -> str | None:
        
        if not comment.properties:
            return None
        
        ref = comment.properties.get("inline-marker-ref")
        if isinstance(ref, str):
            return ref.strip() or None
        if isinstance(ref, dict):
            value = ref.get("value")
            if isinstance(value, str):
                return value.strip() or None
        return None

    def _build_image_urls(
        self,
        image_blocks: list,
        site_url: str | None,
        content_id: str,
    ) -> list[str]:
        """Chunk에 포함된 이미지의 다운로드 URL 목록 생성"""
        if not image_blocks or not site_url:
            return []

        base = site_url.rstrip("/")
        urls: list[str] = []
        for block in image_blocks:
            if block.image_filename:
                urls.append(
                    f"{base}/wiki/download/attachments/{content_id}/{block.image_filename}"
                )
        return urls

    def _absolutize_web_url(self, web_url: str | None, site_url: str | None) -> str | None:
        """Confluence webui 경로를 site_url과 결합해 절대 URL로 만든다."""
        if not web_url:
            return None
        if web_url.startswith("http://") or web_url.startswith("https://"):
            return web_url
        if not site_url:
            return web_url
        return f"{site_url.rstrip('/')}/{web_url.lstrip('/')}"

    # ================================================================
    # Dual Content Strategy
    # ================================================================

    def _build_contextual_content(
        self,
        title: str,
        space_name: str | None,
        labels: list[str],
        author_id: str | None,
        updated_at: str | None,
        section_hierarchy: list[str],
        chunk_body: str,
    ) -> str:
        """
        LLM 답변 생성용 contextual_content 생성

        semantic_content(page_content)는 임베딩 검색에만 사용되고,
        LLM이 답변을 생성할 때는 이 contextual_content를 참조한다.

        각 chunk별로 section_hierarchy가 다르므로
        chunk마다 다른 contextual_content가 생성된다.

        형식:
            Title : API 설계 가이드
            Space: Engineering | Labels: api, design
            Author: user_abc | Last Updated: 2024-02-10
            Section: 인증 > OAuth 2.0

            (chunk 본문)
        """
        lines = [f"Title : {title}"]

        # Space & Labels
        meta_parts = []
        if space_name:
            meta_parts.append(f"Space: {space_name}")
        if labels:
            meta_parts.append(f"Labels: {', '.join(labels)}")
        if meta_parts:
            lines.append(" | ".join(meta_parts))

        # Author & Updated
        info_parts = []
        if author_id:
            info_parts.append(f"Author: {author_id}")
        if updated_at:
            info_parts.append(f"Last Updated: {updated_at}")
        if info_parts:
            lines.append(" | ".join(info_parts))

        # Section hierarchy
        if section_hierarchy:
            lines.append(f"Section: {' > '.join(section_hierarchy)}")

        lines.append("")  # 빈 줄 구분
        lines.append(chunk_body)

        return "\n".join(lines)