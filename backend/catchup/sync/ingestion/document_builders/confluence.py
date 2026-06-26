"""
Confluence Entity -> LangChain Document

page.body.value (Storage Format HTML)
→ ConfluenceStorageParser.parse() → Section 트리
→ ConfluenceChunker.chunk() → Chunk 리스트
→ Comment Injection
    - Inline Comment → marker/selection 매칭으로 해당 Chunk에 삽입
    - 매칭 실패한 Inline Comment → 첫 Chunk에 삽입
    - Footer Comment → 첫 Chunk의 data.parts에 삽입
→ LangChain Document 리스트

- confluence:page:{page_id}:chunk:{chunk_index}
- confluence:blogpost:{page_id}:chunk:{chunk_index}
"""
import json
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

import structlog
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from catchup.connectors.confluence.chunker import Chunk
from catchup.connectors.confluence.chunker import ConfluenceChunker
from catchup.connectors.confluence.schemas import ConfluenceBlogPostResponse
from catchup.connectors.confluence.schemas import ConfluenceCommentResponse
from catchup.connectors.confluence.schemas import ConfluencePageResponse
from catchup.connectors.confluence.storage_parser import ConfluenceStorageParser

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ConfluenceV2CommentPart:
    type: str
    text: str
    comment_id: str | None = None
    status: str | None = None
    author_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    resolution_status: str | None = None
    parent_comment_id: str | None = None
    selection: str | None = None


@dataclass(frozen=True)
class ConfluenceV2PreparedChunk:
    document_id: str
    content_id: str
    entity_type: str
    status: str
    title: str
    body_text: str
    page_content: str
    url: str | None
    space_id: str | None
    space_key: str | None
    space_name: str | None
    parent_page_id: str | None
    parent_type: str | None
    position: int | None
    author_id: str | None
    author_name: str | None
    owner_id: str | None
    created_at: str | None
    updated_at: str | None
    version_number: int | None
    version_author_id: str | None
    version_message: str | None
    version_minor_edit: bool | None
    labels: list[str] = field(default_factory=list)
    chunk_index: int = 0
    chunk_count: int = 0
    section_hierarchy: list[str] = field(default_factory=list)
    has_images: bool = False
    image_urls: list[str] = field(default_factory=list)
    comments: list[ConfluenceV2CommentPart] = field(default_factory=list)


@dataclass(frozen=True)
class ConfluenceInlineCommentInjectionResult:
    unmatched: list[ConfluenceCommentResponse] = field(default_factory=list)
    matched_by_chunk_index: dict[int, list[ConfluenceV2CommentPart]] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ConfluenceTransformResult:
    documents: list[Document]
    v2_prepared_chunks: list[ConfluenceV2PreparedChunk] = field(default_factory=list)


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
            site_url: str | None = None,
            user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:
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
            parent_type=page.parent_type,
            position=page.position,
            author_id=page.author_id,
            owner_id=page.owner_id,
            created_at=page.created_at,
            version=page.version,
            web_url=page.get_web_url(),
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=inline_comments,
            site_url=site_url,
            user_name_map=user_name_map,
        )

    def transform_blogpost(
        self,
        blogpost: ConfluenceBlogPostResponse,
        *,
        space_key: str | None = None,
        space_name: str | None = None,
        labels: list[str] | None = None,
        footer_comments: list[ConfluenceCommentResponse] | None = None,
        site_url: str | None = None,
        user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:
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
            parent_type=None,
            position=None,
            author_id=blogpost.author_id,
            owner_id=None,
            created_at=blogpost.created_at,
            version=blogpost.version,
            web_url=blogpost.get_web_url(),
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=None,
            site_url=site_url,
            user_name_map=user_name_map,
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
        parent_type: str | None,
        position: int | None,
        author_id: str | None,
        owner_id: str | None,
        created_at: str | None,
        version,
        web_url: str | None,
        labels: list[str] | None,
        footer_comments: list[ConfluenceCommentResponse] | None,
        inline_comments: list[ConfluenceCommentResponse] | None,
        site_url: str | None = None,
        user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:

        labels = labels or []

        # 1) Storage HTML 추출
        storage_html = body.value if body else ""
        if not storage_html:
            logger.info(
                "confluence_transform_empty_body",
                connector="confluence",
                entity_type=entity_type,
                content_id=content_id,
                target_id=space_key,
            )
            return ConfluenceTransformResult(documents=[])
        
        web_url = self._absolutize_web_url(web_url, site_url)

        author_name = None
        if author_id and user_name_map:
            author_name = user_name_map.get(author_id)

        # 2) Storage -> Section Tree
        sections = self.parser.parse(storage_html)
        if not sections:
            logger.info(
                "confluence_transform_no_sections",
                connector="confluence",
                entity_type=entity_type,
                content_id=content_id,
                target_id=space_key,
            )
            return ConfluenceTransformResult(documents=[])
        
        # 3) Section 트리 → Chunk 리스트
        chunks = self.chunker.chunk(sections, page_title=title)
        if not chunks:
            return ConfluenceTransformResult(documents=[])

        # 4) Comment Injection
        #    - Inline: marker/selection 매칭 성공 → 해당 chunk에 삽입
        #    - 매칭 실패 Inline → 첫 chunk에 fallback 삽입
        #    - Footer → 첫 chunk의 data.parts에 삽입
        inline_injection = ConfluenceInlineCommentInjectionResult()
        if inline_comments:
            inline_injection = self._inject_inline_comments(chunks, inline_comments)

        footer_comment_parts = self._footer_comment_parts(footer_comments or [])

        # 5. Chunk → LangChain Document 변환
        documents: list[Document] = []
        v2_prepared_chunks: list[ConfluenceV2PreparedChunk] = []
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
                author_name=author_name,
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
                "author_name": author_name,
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
            v2_comments = list(
                inline_injection.matched_by_chunk_index.get(chunk.index, [])
            )
            if chunk.index == 0:
                v2_comments.extend(footer_comment_parts)
            v2_prepared_chunks.append(
                ConfluenceV2PreparedChunk(
                    document_id=doc_id,
                    content_id=content_id,
                    entity_type=entity_type,
                    status=status,
                    title=title,
                    body_text=chunk.body_text,
                    page_content=semantic_content,
                    url=web_url,
                    space_id=space_id,
                    space_key=space_key,
                    space_name=space_name,
                    parent_page_id=parent_page_id,
                    parent_type=parent_type,
                    position=position,
                    author_id=author_id,
                    author_name=author_name,
                    owner_id=owner_id,
                    created_at=created_at,
                    updated_at=updated_at,
                    version_number=version_number,
                    version_author_id=version.author_id if version else None,
                    version_message=version.message if version else None,
                    version_minor_edit=version.minor_edit if version else None,
                    labels=list(labels),
                    chunk_index=chunk.index,
                    chunk_count=total_chunks,
                    section_hierarchy=list(chunk.section_hierarchy),
                    has_images=has_images,
                    image_urls=image_urls,
                    comments=v2_comments,
                )
            )

        image_chunk_count = sum(1 for chunk in chunks if chunk.image_blocks)
        logger.info(
            "confluence_transform_completed",
            connector="confluence",
            entity_type=entity_type,
            content_id=content_id,
            target_id=space_key,
            document_count=len(documents),
            chunk_count=len(chunks),
            v2_prepared_chunk_count=len(v2_prepared_chunks),
            image_chunk_count=image_chunk_count,
            footer_comment_count=len(footer_comments or []),
            inline_comment_count=len(inline_comments or []),
            discussion_chunk_added=False,
        )

        return ConfluenceTransformResult(
            documents=documents,
            v2_prepared_chunks=v2_prepared_chunks,
        )
    
    def _inject_inline_comments(
            self,
            chunks: list[Chunk],
            inline_comments: list[ConfluenceCommentResponse],
    ) -> ConfluenceInlineCommentInjectionResult:
        
        matched_by_chunk_index: dict[int, list[ConfluenceV2CommentPart]] = {}

        if not chunks:
            return ConfluenceInlineCommentInjectionResult()
        
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
                    target_chunk = self._find_chunk_by_selection(chunks, selection)

            # 3) 위치 정보가 깨진 inline comment도 검색 가능한 기존 chunk에 보존한다.
            if target_chunk is None:
                target_chunk = chunks[0]
                logger.info(
                    "confluence_inline_comment_fallback_to_first_chunk",
                    connector="confluence",
                    comment_id=comment.id,
                    marker_ref=marker_ref,
                    selection=self._extract_inline_selection(comment),
                    chunk_index=target_chunk.index,
                )

            target_chunk.content = f"{target_chunk.content}\n{formatted}"
            part = self._comment_part(
                part_type="inline_comment",
                comment=comment,
                text=comment_text,
                selection=self._extract_inline_selection(comment),
            )
            if part is not None:
                matched_by_chunk_index.setdefault(target_chunk.index, []).append(part)

        return ConfluenceInlineCommentInjectionResult(
            matched_by_chunk_index=matched_by_chunk_index,
        )

    def _footer_comment_parts(
        self,
        footer_comments: list[ConfluenceCommentResponse],
    ) -> list[ConfluenceV2CommentPart]:
        parts: list[ConfluenceV2CommentPart] = []
        for comment in footer_comments:
            text = self._extract_comment_text(comment)
            part = self._comment_part(
                part_type="footer_comment",
                comment=comment,
                text=text,
                selection=None,
            )
            if part is not None:
                parts.append(part)
        return parts

    @classmethod
    def _find_chunk_by_selection(
        cls,
        chunks: list[Chunk],
        selection: str,
    ) -> Chunk | None:
        normalized_selection = cls._normalize_for_comment_match(selection)
        for chunk in chunks:
            if selection in chunk.content or selection in chunk.body_text:
                return chunk
            normalized_content = cls._normalize_for_comment_match(chunk.content)
            normalized_body = cls._normalize_for_comment_match(chunk.body_text)
            if normalized_selection and (
                normalized_selection in normalized_content
                or normalized_selection in normalized_body
            ):
                return chunk
        return None

    @staticmethod
    def _normalize_for_comment_match(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _comment_part(
        *,
        part_type: str,
        comment: ConfluenceCommentResponse,
        text: str,
        selection: str | None,
    ) -> ConfluenceV2CommentPart | None:
        normalized = text.strip()
        if not normalized:
            return None
        return ConfluenceV2CommentPart(
            type=part_type,
            text=normalized,
            comment_id=comment.id,
            status=comment.status,
            author_id=comment.author_id,
            created_at=comment.created_at,
            updated_at=comment.version.created_at if comment.version else None,
            resolution_status=comment.resolution_status,
            parent_comment_id=comment.parent_comment_id,
            selection=selection,
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
            return value.strip() if isinstance(value, str) else ""

        # atlas_doc_format(A DF) → JSON을 파싱해 text 노드만 추출
        if comment.body.representation == "atlas_doc_format":
            try:
                adf = json.loads(value) if isinstance(value, str) else value
                if isinstance(adf, (dict, list)):
                    extracted = self._extract_text_from_adf(adf)
                    if extracted:
                        return extracted.strip()
            except Exception as exc:
                # 파싱 실패 시 아래 HTML 처리로 fallback
                logger.debug(
                    "confluence_comment_adf_parse_failed",
                    connector="confluence",
                    comment_id=comment.id,
                    representation=comment.body.representation,
                    exception_type=type(exc).__name__,
                )

        # Storage Format → 텍스트 추출 (태그 제거)
        # dict 형태로 올 경우 문자열로 변환 후 HTML 태그 제거
        soup = BeautifulSoup(str(value), "lxml")
        return soup.get_text(strip=True)

    def _extract_text_from_adf(self, node) -> str:
        """atlas_doc_format(JSON)에서 text 필드만 모아 단일 문자열로 반환"""
        texts: list[str] = []

        def walk(item):
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    texts.append(item["text"])
                content = item.get("content")
                if isinstance(content, list):
                    for child in content:
                        walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)

        walk(node)
        return " ".join(texts)

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

        base = site_url.rstrip("/")
        path = web_url.lstrip("/")
        if base.endswith("/wiki") or path.startswith("wiki/"):
            return f"{base}/{path}"
        return f"{base}/wiki/{path}"

    # ================================================================
    # Dual Content Strategy
    # ================================================================

    def _build_contextual_content(
        self,
        title: str,
        space_name: str | None,
        labels: list[str],
        author_name: str | None,
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
        author_line = author_name or author_id
        if author_line:
            info_parts.append(f"Author: {author_line}")
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
