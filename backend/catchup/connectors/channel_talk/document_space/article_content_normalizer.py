from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping

from bs4 import BeautifulSoup

from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticle,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleRevision,
)

FILE_ATTACHMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".tsv",
    ".zip",
)


class ArticleContentNormalizer:
    """Channel Talk article body 표현을 chunker가 다룰 수 있는 plain text로 정규화한다."""

    def normalize_source_content(
        self,
        source: ChannelTalkDocumentArticle | ChannelTalkDocumentArticleRevision,
    ) -> str:
        # Source 우선순위: rich block body -> plain body -> body_html -> summary fallback.
        # 기존 API 응답 형태가 섞여 들어와도 downstream chunker는 하나의 text만 받는다.
        if isinstance(source.body, (list, tuple, Mapping)):
            block_text = self._normalize_block_body(source.body)
            if block_text:
                return block_text
        if isinstance(source.body, str) and source.body.strip():
            return self._normalize_plain_text(source.body)
        if source.body_html and source.body_html.strip():
            return self._normalize_html(source.body_html)
        fallback_parts = [
            source.summary,
            source.subtitle,
            source.title,
        ]
        return self._normalize_plain_text(
            "\n\n".join(part for part in fallback_parts if part)
        )

    @staticmethod
    def _normalize_html(value: str) -> str:
        # HTML 정규화 단계: 검색에 불필요한 tag를 제거하고,
        # table/media/link는 text context가 남도록 markdown-like text로 변환한다.
        soup = BeautifulSoup(value, "lxml")
        for element in soup(["script", "style", "noscript", "svg"]):
            element.decompose()
        for table in soup.find_all("table"):
            table.replace_with(
                "\n" + ArticleContentNormalizer._format_html_table(table) + "\n"
            )
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            for image in heading.find_all("img"):
                label = image.get("alt") or image.get("title")
                image.replace_with(label.strip() if isinstance(label, str) else "")
        for media in soup.find_all(["figure"]):
            media_text = ArticleContentNormalizer._format_html_figure(media)
            if media_text:
                media.replace_with(f"\n{media_text}\n")
        for media in soup.find_all(["img", "video"]):
            media_text = ArticleContentNormalizer._format_html_media_element(
                media
            )
            media.replace_with(f"\n{media_text}\n" if media_text else "")
        for media in soup.find_all(["iframe", "embed"]):
            src = (
                media.get("src")
                or media.get("href")
                or media.get("data-node-attrs-src")
            )
            media_text = ArticleContentNormalizer._format_link_text(
                "Embed",
                src,
            )
            media.replace_with(f"\n{media_text}\n" if media_text else "")
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(heading.name[1])
            text = heading.get_text(" ", strip=True)
            if text:
                heading.string = f"{'#' * level} {text}"
        for link in soup.find_all("a"):
            label = link.get_text(" ", strip=True)
            href = link.get("href")
            if ArticleContentNormalizer._is_html_file_attachment(link):
                link.replace_with(
                    ArticleContentNormalizer._format_file_attachment(
                        ArticleContentNormalizer._html_file_name(link)
                    )
                )
                continue
            if link.get("data-node-type") == "embed":
                label = label if label and label != href else "Embed"
            link_text = ArticleContentNormalizer._format_link_text(
                label,
                href,
            )
            if link_text:
                link.replace_with(link_text)
        block_tags = ["br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"]
        for breaker in soup.find_all(block_tags):
            breaker.append("\n")
        return ArticleContentNormalizer._normalize_plain_text(
            soup.get_text("\n")
        )

    @staticmethod
    def _normalize_block_body(value: object) -> str:
        parts = list(ArticleContentNormalizer._iter_block_text_blocks(value))
        return ArticleContentNormalizer._normalize_plain_text(
            "\n\n".join(parts)
        )

    @staticmethod
    def _iter_block_text_blocks(value: object) -> Iterable[str]:
        # Rich block 순회 단계: node type별 의미를 text로 보존한다.
        # 지원하지 않는 wrapper node는 content를 재귀적으로 펼쳐 손실을 줄인다.
        if isinstance(value, str):
            text = value.strip()
            if text:
                yield text
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                yield from ArticleContentNormalizer._iter_block_text_blocks(
                    item
                )
            return
        if not isinstance(value, Mapping):
            return

        node_type = str(value.get("type") or "").strip()
        attrs = ArticleContentNormalizer._mapping_value(value.get("attrs"))
        if node_type == "heading":
            text = ArticleContentNormalizer._extract_block_inline_text(value)
            if text:
                level = ArticleContentNormalizer._int_value(
                    attrs.get("level"),
                    default=1,
                )
                yield f"{'#' * min(max(level, 1), 6)} {text}"
            return
        if node_type in {"text", "paragraph"}:
            text = ArticleContentNormalizer._extract_block_inline_text(value)
            if text:
                yield text
            return
        if node_type in {"image", "video"}:
            media_text = (
                ArticleContentNormalizer._format_media_block_from_attrs(
                    node_type=node_type,
                    attrs=attrs,
                )
            )
            if media_text:
                yield media_text
            return
        if node_type == "embed":
            embed_text = ArticleContentNormalizer._format_link_text(
                "Embed",
                ArticleContentNormalizer._first_text(
                    attrs,
                    "src",
                    "url",
                    "href",
                ),
            )
            if embed_text:
                yield embed_text
            return
        if node_type in {"file", "attachment", "attachments"}:
            yield ArticleContentNormalizer._format_file_attachment(
                ArticleContentNormalizer._file_name_from_attrs(attrs)
            )
            return
        if node_type == "table":
            table_text = ArticleContentNormalizer._format_block_table(value)
            if table_text:
                yield table_text
            return
        if node_type in {"bullets", "bulletList"}:
            list_text = ArticleContentNormalizer._format_block_list(
                value,
                ordered=False,
            )
            if list_text:
                yield list_text
            return
        if node_type == "orderedList":
            list_text = ArticleContentNormalizer._format_block_list(
                value,
                ordered=True,
            )
            if list_text:
                yield list_text
            return
        if node_type in {"code", "codeBlock"}:
            text = ArticleContentNormalizer._extract_block_inline_text(value)
            if text:
                yield f"```\n{text}\n```"
            return

        child_blocks = list(
            ArticleContentNormalizer._iter_block_text_blocks(
                value.get("content", ())
            )
        )
        if child_blocks:
            yield "\n".join(child_blocks)
            return

        text = ArticleContentNormalizer._extract_block_inline_text(value)
        if text:
            yield text

    @staticmethod
    def _extract_block_inline_text(value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            return "".join(
                ArticleContentNormalizer._extract_block_inline_text(item)
                for item in value
            ).strip()
        if not isinstance(value, Mapping):
            return ""

        node_type = str(value.get("type") or "").strip()
        attrs = ArticleContentNormalizer._mapping_value(value.get("attrs"))
        if node_type == "plain":
            text = ArticleContentNormalizer._first_text(
                attrs,
                "text",
                "name",
                "title",
            )
            return ArticleContentNormalizer._apply_link_marks(
                text,
                value.get("marks"),
            )
        if node_type == "emoji":
            return ArticleContentNormalizer._first_text(
                attrs,
                "name",
                "text",
            )
        if node_type in {"image", "video"}:
            return ArticleContentNormalizer._format_media_block_from_attrs(
                node_type=node_type,
                attrs=attrs,
            )
        if node_type in {"file", "attachment", "attachments"}:
            return ArticleContentNormalizer._format_file_attachment(
                ArticleContentNormalizer._file_name_from_attrs(attrs)
            )
        if node_type == "embed":
            return ArticleContentNormalizer._format_link_text(
                "Embed",
                ArticleContentNormalizer._first_text(
                    attrs,
                    "src",
                    "url",
                    "href",
                ),
            )

        if "content" in value:
            return "".join(
                ArticleContentNormalizer._extract_block_inline_text(item)
                for item in ArticleContentNormalizer._sequence_value(
                    value.get("content")
                )
            ).strip()
        return ArticleContentNormalizer._first_text(
            attrs,
            "text",
            "plainText",
            "title",
            "name",
            "label",
        )

    @staticmethod
    def _format_block_table(value: Mapping[str, object]) -> str:
        # Table 변환 단계: cell text만 추출해 markdown table로 만든다.
        # 이후 chunker가 table block을 별도 splitting 대상으로 인식한다.
        rows: list[list[str]] = []
        for row in ArticleContentNormalizer._sequence_value(
            value.get("content")
        ):
            if not isinstance(row, Mapping):
                continue
            cells = []
            for cell in ArticleContentNormalizer._sequence_value(
                row.get("content")
            ):
                cell_text = ArticleContentNormalizer._extract_block_cell_text(
                    cell
                )
                cells.append(cell_text)
            if cells:
                rows.append(cells)
        return ArticleContentNormalizer._format_markdown_table(rows)

    @staticmethod
    def _extract_block_cell_text(value: object) -> str:
        blocks = list(ArticleContentNormalizer._iter_block_text_blocks(value))
        if blocks:
            return " ".join(block.replace("\n", " ") for block in blocks).strip()
        return ArticleContentNormalizer._extract_block_inline_text(value)

    @staticmethod
    def _format_block_list(value: Mapping[str, object], *, ordered: bool) -> str:
        lines: list[str] = []
        start = ArticleContentNormalizer._int_value(
            ArticleContentNormalizer._mapping_value(value.get("attrs")).get(
                "start"
            ),
            default=1,
        )
        for index, item in enumerate(
            ArticleContentNormalizer._sequence_value(value.get("content")),
            start=start,
        ):
            item_blocks = list(
                ArticleContentNormalizer._iter_block_text_blocks(item)
            )
            item_text = "\n".join(item_blocks).strip()
            if not item_text:
                continue
            marker = f"{index}. " if ordered else "- "
            item_lines = item_text.splitlines()
            lines.append(marker + item_lines[0])
            lines.extend(f"  {line}" for line in item_lines[1:])
        return "\n".join(lines)

    @staticmethod
    def _format_html_table(table) -> str:
        rows: list[list[str]] = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                cells = row.find_all(["th", "td"])
            row_values = [cell.get_text(" ", strip=True) for cell in cells]
            if row_values:
                rows.append(row_values)
        return ArticleContentNormalizer._format_markdown_table(rows)

    @staticmethod
    def _format_markdown_table(rows: list[list[str]]) -> str:
        rows = [
            [cell.strip() for cell in row]
            for row in rows
            if any(cell.strip() for cell in row)
        ]
        if not rows:
            return ""
        column_count = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
        header = normalized_rows[0]
        data_rows = normalized_rows[1:]
        lines = [
            "| "
            + " | ".join(
                ArticleContentNormalizer._escape_markdown_table_cell(cell)
                for cell in header
            )
            + " |",
            "| " + " | ".join("---" for _ in range(column_count)) + " |",
        ]
        for row in data_rows:
            lines.append(
                "| "
                + " | ".join(
                    ArticleContentNormalizer._escape_markdown_table_cell(cell)
                    for cell in row
                )
                + " |"
            )
        return "\n".join(lines)

    @staticmethod
    def _escape_markdown_table_cell(value: str) -> str:
        return " ".join(value.split()).replace("|", "\\|")

    @staticmethod
    def _format_html_figure(figure) -> str:
        media = figure.find(["img", "video"])
        if media is None:
            return ""
        caption = ""
        figcaption = figure.find("figcaption")
        if figcaption is not None:
            caption = figcaption.get_text(" ", strip=True)
        return ArticleContentNormalizer._format_html_media_element(
            media,
            caption=caption,
        )

    @staticmethod
    def _format_html_media_element(media, *, caption: str | None = None) -> str:
        node_type = "video" if media.name == "video" else "image"
        attrs = {
            "alt": media.get("alt"),
            "title": media.get("title"),
            "src": media.get("src") or media.get("data-node-attrs-src"),
            "caption": caption,
        }
        return ArticleContentNormalizer._format_media_block_from_attrs(
            node_type=node_type,
            attrs=attrs,
        )

    @staticmethod
    def _format_media_block_from_attrs(
        *,
        node_type: str,
        attrs: Mapping[str, object],
    ) -> str:
        # Media 변환 단계: 원본 binary를 저장하지 않고 caption/source/file name만 남긴다.
        # 검색 context에는 "무엇이 첨부됐는지"가 드러나는 것이 더 중요하다.
        label = "Video" if node_type == "video" else "Image"
        file_name = ArticleContentNormalizer._first_text(
            attrs,
            "alt",
            "title",
            "name",
            "fileName",
            "file_name",
            "filename",
        )
        caption = ArticleContentNormalizer._caption_text(attrs.get("caption"))
        lines = [f"[{label}] {file_name}" if file_name else f"[{label}]"]
        if caption:
            lines.append(f"Caption: {caption}")
        return "\n".join(lines)

    @staticmethod
    def _caption_text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        blocks = list(ArticleContentNormalizer._iter_block_text_blocks(value))
        if blocks:
            return " ".join(blocks).strip()
        return ArticleContentNormalizer._extract_block_inline_text(value)

    @staticmethod
    def _format_link_text(label: object, href: object) -> str:
        text = str(label or "").strip()
        url = str(href or "").strip()
        if text and url and url not in text:
            return f"{text} ({url})"
        return text or url

    @staticmethod
    def _format_file_attachment(file_name: object) -> str:
        normalized = str(file_name or "").strip() or "첨부 파일"
        return f"{normalized} [파일 첨부]"

    @staticmethod
    def _html_file_name(link) -> str:
        for key in (
            "download",
            "title",
            "data-node-attrs-name",
            "data-node-attrs-file-name",
            "data-node-attrs-filename",
        ):
            value = link.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        label = link.get_text(" ", strip=True)
        if label:
            return label
        href = str(link.get("href") or "").rstrip("/")
        return href.rsplit("/", 1)[-1]

    @staticmethod
    def _is_html_file_attachment(link) -> bool:
        node_type = str(link.get("data-node-type") or "").strip()
        if node_type in {"file", "attachment"}:
            return True
        mime = str(link.get("data-node-attrs-mime") or link.get("type") or "").lower()
        if mime and not mime.startswith(("text/html", "image/", "video/")):
            return True
        href = str(link.get("href") or "").lower()
        return any(
            href.split("?", 1)[0].endswith(ext) for ext in FILE_ATTACHMENT_EXTENSIONS
        )

    @staticmethod
    def _file_name_from_attrs(attrs: Mapping[str, object]) -> str:
        file_name = ArticleContentNormalizer._first_text(
            attrs,
            "name",
            "fileName",
            "file_name",
            "filename",
            "title",
            "alt",
        )
        if file_name:
            return file_name
        src = ArticleContentNormalizer._first_text(
            attrs,
            "src",
            "url",
            "href",
        ).rstrip("/")
        if src:
            return src.rsplit("/", 1)[-1]
        return ""

    @staticmethod
    def _apply_link_marks(text: str, marks: object) -> str:
        if not text:
            return ""
        for mark in ArticleContentNormalizer._sequence_value(marks):
            if not isinstance(mark, Mapping):
                continue
            if str(mark.get("type") or "") != "link":
                continue
            attrs = ArticleContentNormalizer._mapping_value(mark.get("attrs"))
            href = ArticleContentNormalizer._first_text(
                attrs,
                "href",
                "url",
                "src",
            )
            return ArticleContentNormalizer._format_link_text(
                text,
                href,
            )
        return text

    @staticmethod
    def _first_text(source: Mapping[str, object], *keys: str) -> str:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _mapping_value(value: object) -> Mapping[str, object]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _sequence_value(value: object) -> tuple[object, ...]:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        if value is None:
            return ()
        return (value,)

    @staticmethod
    def _int_value(value: object, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_plain_text(value: str) -> str:
        lines = [" ".join(line.split()) for line in value.splitlines()]
        compacted: list[str] = []
        previous_blank = False
        for line in lines:
            if not line:
                if not previous_blank and compacted:
                    compacted.append("")
                previous_blank = True
                continue
            compacted.append(line)
            previous_blank = False
        return "\n".join(compacted).strip()
