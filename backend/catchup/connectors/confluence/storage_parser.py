"""
XHTML -> Section Tree Parser
"""

import logging
from dataclasses import dataclass
from dataclasses import field

from bs4 import BeautifulSoup
from bs4 import NavigableString
from bs4 import Tag

logger = logging.getLogger(__name__)

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

PANEL_TYPE_MAPPING = {
    "info": "정보",
    "warning": "경고",
    "note": "참고",
    "tip": "팁",
}

IMAGE_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

@dataclass
class ContentBlock:
    block_type: str
    text: str
    language: str | None = None     # Code Block 전용
    panel_type: str | None = None   # Panel 전용
    image_filename: str | None = None
    image_media_type: str | None = None
    inline_comment_refs: list[str] = field(default_factory=list)

@dataclass
class Section:
    """
    heading level : 0 = root, 1 = h1 ...
    heading text : heading에 해당하는 텍스트
    content_blocks : 이 섹션에 속하는 실제 콘텐츠
    children : 하위 Section 리스트
    """
    heading_level: int
    heading_text: str
    content_blocks: list[ContentBlock] = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)


class ConfluenceStorageParser:
    
    def parse(self, storage_html: str) -> list[Section]:

        if not storage_html or not storage_html.strip():
            return []
        
        soup = BeautifulSoup(storage_html, "lxml")
        body = soup.body if soup.body else soup

        root = Section(heading_level=0, heading_text="")

        stack: list[tuple[Section, int]] = [(root, 0)]

        for element in body.children:
            if isinstance(element, NavigableString):
                text = element.strip()
                if text:
                    stack[-1][0].content_blocks.append(
                        ContentBlock(block_type="text", text=text)
                    )
                continue

            if not isinstance(element, Tag):
                continue
            
            tag_name = element.name.lower() if element.name else ""


            # Heading -> 새로운 Section
            if tag_name in HEADING_TAGS:
                level = int(tag_name[1])
                heading_text = element.get_text(strip=True)

                new_section = Section(
                    heading_level=level,
                    heading_text=heading_text,
                )

                while len(stack) > 1 and stack[-1][1] >= level:
                    stack.pop()
                
                stack[-1][0].children.append(new_section)
                stack.append((new_section, level))
            
            # Heading이 아닌 요소 -> 현재 Section의 Content Block
            else:
                blocks = self._parse_element(element)
                for block in blocks:
                    stack[-1][0].content_blocks.append(block)
        
        return self._finalize_root(root)
    
    def _finalize_root(self, root: Section) -> list[Section]:
        """
        1. Heading으로 시작 -> Children 반환
        2. Heading 전 Intro Section 존재 -> Intro + Children
        3. Heading 없음 -> root
        """

        if not root.content_blocks and not root.children:
            return []
        
        if root.content_blocks and not root.children:
            return [root]
        
        if root.content_blocks:
            intro_section = Section(
                heading_level=0,
                heading_text="",
                content_blocks=root.content_blocks,
            )
            return [intro_section] + root.children
        
        return root.children
    
    def _parse_element(self, element: Tag) -> list[ContentBlock]:
        """
        HTML 요소 1개 → ContentBlock 리스트로 변환

        대부분 1개의 ContentBlock을 반환하지만,
        <p> 안에 이미지가 있거나, expand 매크로처럼 여러 블록을 생성하는 경우
        복수의 ContentBlock을 반환할 수 있다.
        """
        tag_name = element.name.lower() if element.name else ""

        if tag_name == "p":
            return self._parse_paragraph(element)
        elif tag_name in ("ul", "ol"):
            return [self._parse_list(element)]
        elif tag_name == "table":
            return [self._parse_table(element)]
        elif tag_name == "ac:structured-macro":
            return self._parse_macro(element)
        elif tag_name == "ac:image":
            return [self._parse_image(element)]
        elif tag_name == "div":
            return self._parse_div(element)
        elif tag_name == "blockquote":
            return self._parse_blockquote(element)
        elif tag_name == "hr":
            return [ContentBlock(block_type="text", text="---")]
        elif tag_name == "pre":
            return [ContentBlock(block_type="code", text=element.get_text())]
        else:
            # 알 수 없는 태그는 텍스트만 추출
            text = element.get_text(strip=True)
            if text:
                return [ContentBlock(block_type="text", text=text)]
            return []
        
    def _parse_paragraph(self, element: Tag) -> list[ContentBlock]:
        """
        <p> 태그 파싱

        <p> 안에는 텍스트뿐 아니라 <a>, <ac:image>, <ac:link> 등
        다양한 인라인 요소가 섞여 있을 수 있다.

        특히 <ac:image>가 있으면 이미지 블록을 별도로 분리한다.
        (이미지는 별도 ContentBlock으로 만들어야 chunker에서 추적 가능)

        예시:
            <p>텍스트 <ac:image><ri:attachment ri:filename="img.png"/></ac:image> 후속텍스트</p>
            → [ContentBlock("텍스트"), ContentBlock(image, "img.png"), ContentBlock("후속텍스트")]
        """
        blocks: list[ContentBlock] = []
        text_parts: list[str] = []  # 현재까지 모은 인라인 텍스트 조각들
        collected_refs: list[str] = []

        for child in element.children:
            if isinstance(child, NavigableString):
                text_parts.append(str(child))

            elif isinstance(child, Tag):
                if child.name == "ac:image":
                    # 이미지 앞의 텍스트가 있으면 먼저 text 블록으로 확정
                    if text_parts:
                        text = "".join(text_parts).strip()
                        if text:
                            blocks.append(ContentBlock(
                                block_type="text", text=text,
                                inline_comment_refs = collected_refs,
                            ))
                        text_parts = []
                        collected_refs = []
                    # 이미지는 별도 블록으로 분리
                    blocks.append(self._parse_image(child))

                elif child.name == "ac:emoticon":
                    pass  # 이모티콘 무시

                elif child.name == "ac:inline-comment-marker":
                    ref = child.get("ac:ref")
                    if ref:
                        collected_refs.append(ref)
                    text_parts.append(self._extract_inline_text(child, collected_refs))

                elif child.name == "ac:link":
                    text_parts.append(self._extract_ac_link_text(child))

                elif child.name == "a":
                    text_parts.append(self._extract_link_text(child))

                elif child.name == "ac:structured-macro":
                    # <p> 안에 매크로가 있는 경우 (인라인 매크로)
                    if text_parts:
                        text = "".join(text_parts).strip()
                        if text:
                            blocks.append(ContentBlock(
                                block_type="text", text=text,
                                inline_comment_refs=collected_refs,
                            ))
                        text_parts = []
                        collected_refs = []
                    blocks.extend(self._parse_macro(child))

                else:
                    # <strong>, <em>, <span> 등 인라인 서식 태그
                    text_parts.append(self._extract_inline_text(child, collected_refs))

        # 남은 텍스트 처리
        if text_parts:
            text = "".join(text_parts).strip()
            if text:
                blocks.append(ContentBlock(
                    block_type="text", text=text,
                    inline_comment_refs=collected_refs,
                ))

        return blocks

    def _parse_list(self, element: Tag) -> ContentBlock:
        """
        <ul>/<ol> → ContentBlock(type="list")

        리스트 전체를 하나의 ContentBlock으로 만든다.

        중첩 리스트도 재귀적으로 처리하며 들여쓰기로 표현:
            - 항목 1
              - 하위 항목 1-1
              - 하위 항목 1-2
            - 항목 2
        """
        lines = self._extract_list_items(element, level=0)
        return ContentBlock(block_type="list", text="\n".join(lines))

    def _extract_list_items(self, element: Tag, level: int) -> list[str]:
        """리스트 아이템을 재귀적으로 추출하여 Markdown 형식 문자열로 변환"""
        lines: list[str] = []
        is_ordered = element.name.lower() == "ol"
        indent = "  " * level  # 중첩 레벨에 따라 들여쓰기
        counter = 1

        for li in element.find_all("li", recursive=False):
            # li 직접 자식 중 텍스트만 추출 (중첩 리스트 <ul>/<ol>은 건너뜀)
            text_parts: list[str] = []
            for child in li.children:
                if isinstance(child, NavigableString):
                    text_parts.append(str(child))
                elif isinstance(child, Tag):
                    if child.name in ("ul", "ol"):
                        continue  # 중첩 리스트는 아래에서 별도 처리
                    elif child.name == "a":
                        text_parts.append(self._extract_link_text(child))
                    elif child.name == "ac:link":
                        text_parts.append(self._extract_ac_link_text(child))
                    else:
                        text_parts.append(child.get_text())

            text = "".join(text_parts).strip()
            if text:
                prefix = f"{counter}." if is_ordered else "-"
                lines.append(f"{indent}{prefix} {text}")
                counter += 1

            # 중첩 리스트를 재귀 처리
            for nested in li.find_all(["ul", "ol"], recursive=False):
                lines.extend(self._extract_list_items(nested, level + 1))

        return lines

    def _parse_table(self, element: Tag) -> ContentBlock:
        """
        <table> → Markdown 표 형식 ContentBlock

        변환 결과 예시:
            | Column A | Column B |
            | --- | --- |
            | Data 1 | Data 2 |
            | Data 3 | Data 4 |

        첫 행(<th> 또는 첫 <tr>)을 헤더로 사용하고,
        열 수가 맞지 않으면 빈 셀로 채운다.
        """
        rows: list[list[str]] = []

        for tr in element.find_all("tr"):
            cells: list[str] = []
            for cell in tr.find_all(["th", "td"]):
                cell_text = cell.get_text(strip=True)
                cells.append(cell_text)
            if cells:
                rows.append(cells)

        if not rows:
            return ContentBlock(block_type="table", text="")

        lines: list[str] = []

        # 첫 행 = 헤더
        header = rows[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        # 나머지 행 = 데이터
        for row in rows[1:]:
            # 열 수가 헤더보다 적으면 빈 문자열로 채움
            while len(row) < len(header):
                row.append("")
            lines.append("| " + " | ".join(row[: len(header)]) + " |")

        return ContentBlock(block_type="table", text="\n".join(lines))

    def _parse_macro(self, element: Tag) -> list[ContentBlock]:
        """
        <ac:structured-macro ac:name="..."> 디스패처

        Confluence 매크로는 ac:name 속성으로 종류를 구분한다.
        각 매크로 타입별로 전용 파서 메서드에 위임한다.
        """
        macro_name = element.get("ac:name", "")

        if macro_name == "code":
            return [self._parse_code_macro(element)]
        elif macro_name in ("info", "warning", "note", "tip"):
            return [self._parse_panel_macro(element, macro_name)]
        elif macro_name == "expand":
            return self._parse_expand_macro(element)
        elif macro_name in ("toc", "anchor"):
            return []  # 목차, 앵커 매크로는 무시
        elif macro_name == "jira":
            return self._parse_jira_macro(element)
        else:
            # 알 수 없는 매크로: <ac:rich-text-body> 내부 텍스트만 추출
            body = element.find("ac:rich-text-body")
            if body:
                text = body.get_text(strip=True)
                if text:
                    return [ContentBlock(block_type="text", text=text)]
            return []

    def _parse_code_macro(self, element: Tag) -> ContentBlock:
        """
        코드 블록 매크로 파싱

        Storage Format 구조:
            <ac:structured-macro ac:name="code">
                <ac:parameter ac:name="language">python</ac:parameter>
                <ac:plain-text-body><![CDATA[print("hello")]]></ac:plain-text-body>
            </ac:structured-macro>

        → ```python
          print("hello")
          ```
        """
        # language 파라미터 추출
        language = None
        for param in element.find_all("ac:parameter"):
            if param.get("ac:name") == "language":
                language = param.get_text(strip=True)
                break

        # 코드 본문 추출
        code_body = element.find("ac:plain-text-body")
        code_text = code_body.get_text() if code_body else ""

        # Markdown 코드 블록 포맷으로 변환
        lang_str = language or ""
        formatted = f"```{lang_str}\n{code_text}\n```"

        return ContentBlock(
            block_type="code",
            text=formatted,
            language=language,
        )

    def _parse_panel_macro(self, element: Tag, panel_type: str) -> ContentBlock:
        """
        Info/Warning/Note/Tip 패널 매크로 파싱

        Storage Format 구조:
            <ac:structured-macro ac:name="info">
                <ac:rich-text-body><p>이 API는 인증이 필요합니다.</p></ac:rich-text-body>
            </ac:structured-macro>

        → [정보] 이 API는 인증이 필요합니다.
        """
        body = element.find("ac:rich-text-body")
        text = body.get_text(strip=True) if body else ""

        label = PANEL_TYPE_MAPPING.get(panel_type, panel_type)
        formatted = f"[{label}] {text}"

        return ContentBlock(
            block_type="panel",
            text=formatted,
            panel_type=panel_type,
        )

    def _parse_expand_macro(self, element: Tag) -> list[ContentBlock]:
        """
        접기/펼치기(Expand) 매크로 파싱

        내부에 <p>, <table> 등이 있으면 재귀적으로 파싱한다.

        Storage Format 구조:
            <ac:structured-macro ac:name="expand">
                <ac:parameter ac:name="title">상세 정보</ac:parameter>
                <ac:rich-text-body>
                    <p>접힌 내용...</p>
                </ac:rich-text-body>
            </ac:structured-macro>

        → [ContentBlock("▶ 상세 정보"), ContentBlock("접힌 내용...")]
        """
        # 접기 제목 추출
        title = ""
        for param in element.find_all("ac:parameter"):
            if param.get("ac:name") == "title":
                title = param.get_text(strip=True)
                break

        if not title:
            title = "Details"

        blocks: list[ContentBlock] = []
        blocks.append(ContentBlock(block_type="expand", text=f"▶ {title}"))

        # 내부 콘텐츠 재귀 파싱
        body = element.find("ac:rich-text-body")
        if body:
            for child in body.children:
                if isinstance(child, Tag):
                    blocks.extend(self._parse_element(child))
                elif isinstance(child, NavigableString):
                    text = child.strip()
                    if text:
                        blocks.append(ContentBlock(block_type="text", text=text))

        return blocks

    def _parse_image(self, element: Tag) -> ContentBlock:
        """
        <ac:image> 태그 파싱

        Confluence 이미지는 2가지 형태:
        1. 첨부파일 이미지: <ri:attachment ri:filename="diagram.png"/>
        2. 외부 URL 이미지: <ri:url ri:value="https://..."/>

        image_filename과 image_media_type은 나중에 transformers.py에서
        Attachment API로 실제 이미지를 다운로드하고
        Cohere Embed v4 base64 Data URI를 생성할 때 사용된다.
        """
        filename = None
        media_type = None

        # 첨부파일 이미지에서 파일명 추출
        attachment = element.find("ri:attachment")
        if attachment:
            filename = attachment.get("ri:filename")

        # 외부 URL 이미지
        url_tag = element.find("ri:url")
        external_url = url_tag.get("ri:value") if url_tag else None

        # alt 텍스트
        alt_text = element.get("ac:alt", "")

        # 확장자로 MIME 타입 추론 (base64 Data URI 생성에 필요)
        if filename:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            media_type = IMAGE_MEDIA_TYPES.get(ext)

        # 텍스트 표현 생성
        if filename:
            text = f"[이미지: {filename}]"
            if alt_text:
                text = f"[이미지: {filename} - {alt_text}]"
        elif external_url:
            text = f"[이미지: {external_url}]"
        else:
            text = "[이미지]"

        return ContentBlock(
            block_type="image",
            text=text,
            image_filename=filename,
            image_media_type=media_type,
        )

    def _parse_jira_macro(self, element: Tag) -> list[ContentBlock]:
        """Confluence 문서에 삽입된 Jira 이슈 매크로 파싱"""
        key = ""
        for param in element.find_all("ac:parameter"):
            if param.get("ac:name") == "key":
                key = param.get_text(strip=True)
                break

        if key:
            return [ContentBlock(block_type="text", text=f"[Jira: {key}]")]
        return []

    def _parse_div(self, element: Tag) -> list[ContentBlock]:
        """<div> 태그 - 래퍼 역할이므로 내부 자식 요소를 재귀 파싱"""
        blocks: list[ContentBlock] = []
        for child in element.children:
            if isinstance(child, Tag):
                blocks.extend(self._parse_element(child))
            elif isinstance(child, NavigableString):
                text = child.strip()
                if text:
                    blocks.append(ContentBlock(block_type="text", text=text))
        return blocks

    def _parse_blockquote(self, element: Tag) -> list[ContentBlock]:
        """<blockquote> → Markdown 인용 형식 (> 접두사)"""
        text = element.get_text(strip=True)
        if text:
            quoted = "\n".join(f"> {line}" for line in text.split("\n"))
            return [ContentBlock(block_type="text", text=quoted)]
        return []

    # ================================================================
    # 인라인 텍스트 추출 헬퍼
    # ================================================================

    def _extract_inline_text(
        self, element: Tag, refs_out: list[str] | None = None,
    ) -> str:
        parts: list[str] = []
        for child in element.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                if child.name == "ac:inline-comment-marker":
                    ref = child.get("ac:ref")
                    if ref and refs_out is not None:
                        refs_out.append(ref)
                    parts.append(child.get_text())
                elif child.name == "a":
                    parts.append(self._extract_link_text(child))
                elif child.name == "ac:link":
                    parts.append(self._extract_ac_link_text(child))
                elif child.name == "ac:image":
                    attachment = child.find("ri:attachment")
                    if attachment:
                        fn = attachment.get("ri:filename", "")
                        parts.append(f"[이미지: {fn}]")
                else:
                    parts.append(self._extract_inline_text(child, refs_out))
        return "".join(parts)

    def _extract_link_text(self, element: Tag) -> str:
        """
        <a href="...">텍스트</a> → [텍스트](URL) 형식으로 변환

        URL이 텍스트와 동일하면 URL만 반환 (중복 방지)
        """
        text = element.get_text(strip=True)
        href = element.get("href", "")
        if href and text and href != text:
            return f"[{text}]({href})"
        elif text:
            return text
        elif href:
            return href
        return ""

    def _extract_ac_link_text(self, element: Tag) -> str:
        """
        <ac:link> Confluence 내부 링크에서 텍스트만 추출

        내부 링크는 URL이 상대경로이므로 텍스트만 사용한다.

        내부 구조 (3가지 패턴):
        1. <ac:link-body>표시 텍스트</ac:link-body>
        2. <ac:plain-text-link-body>텍스트</ac:plain-text-link-body>
        3. <ri:page ri:content-title="페이지 제목"/>
        """
        link_body = element.find("ac:link-body")
        if link_body:
            return link_body.get_text(strip=True)

        plain_body = element.find("ac:plain-text-link-body")
        if plain_body:
            return plain_body.get_text(strip=True)

        page_ref = element.find("ri:page")
        if page_ref:
            return page_ref.get("ri:content-title", "")

        return element.get_text(strip=True)