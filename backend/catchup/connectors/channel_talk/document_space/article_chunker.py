from __future__ import annotations

from dataclasses import dataclass

ARTICLE_CHUNK_TARGET_CHARS = 2000
ARTICLE_CHUNK_MAX_CHARS = 4000
ARTICLE_CHUNK_MIN_CHARS = 400


@dataclass
class _ArticleContentBlock:
    block_type: str
    text: str


@dataclass
class _ArticleLeafSection:
    hierarchy: list[str]
    content_blocks: list[_ArticleContentBlock]
    parent_key: str


class ArticleChunker:
    """정규화된 article text를 heading hierarchy를 보존하는 chunk로 분할한다."""

    def chunk_article_content(self, *, header: str, body: str) -> tuple[str, ...]:
        # Chunking 전체 흐름: section 구성 -> 작은 section 병합 -> 큰 section 분할 -> 최종 chunk text 생성.
        # header 길이를 budget에서 제외해 title/context가 붙어도 max size를 넘지 않게 한다.
        budget = self._article_chunk_budget(header)
        leaves = self._build_article_leaf_sections(body)
        if not leaves:
            return (header,)

        merged = self._merge_small_article_sections(leaves, max_chars=budget["max"])
        split = self._split_large_article_sections(
            merged,
            target_chars=budget["target"],
            max_chars=budget["max"],
        )
        post_merged = self._merge_post_split_article_sections(
            split,
            max_chars=budget["max"],
        )
        chunks = self._build_article_chunks(
            header=header,
            leaves=post_merged,
        )
        return tuple(chunks) or (header,)

    @staticmethod
    def _article_chunk_budget(header: str) -> dict[str, int]:
        return {
            "target": max(
                ARTICLE_CHUNK_TARGET_CHARS - len(header) - 2,
                ARTICLE_CHUNK_MIN_CHARS,
            ),
            "max": max(
                ARTICLE_CHUNK_MAX_CHARS - len(header) - 2,
                ARTICLE_CHUNK_MIN_CHARS,
            ),
        }

    def _build_article_leaf_sections(self, body: str) -> list[_ArticleLeafSection]:
        # Section 구성 단계: markdown heading을 hierarchy로 추적하고,
        # heading 사이의 paragraph들을 하나의 leaf section으로 모은다.
        paragraphs = self._split_paragraphs(body)
        leaves: list[_ArticleLeafSection] = []
        hierarchy: list[str] = []
        blocks: list[_ArticleContentBlock] = []

        def flush() -> None:
            nonlocal blocks
            if not blocks:
                return
            leaves.append(
                _ArticleLeafSection(
                    hierarchy=list(hierarchy),
                    content_blocks=blocks,
                    parent_key=" > ".join(hierarchy[:-1]),
                )
            )
            blocks = []

        for paragraph in paragraphs:
            heading = self._parse_article_heading(paragraph)
            if heading is not None:
                flush()
                level, text = heading
                if level is None:
                    hierarchy = [text]
                else:
                    hierarchy = hierarchy[: max(level - 1, 0)] + [text]
                continue

            blocks.append(
                _ArticleContentBlock(
                    block_type=self._infer_article_block_type(paragraph),
                    text=paragraph,
                )
            )

        flush()
        return leaves

    @staticmethod
    def _parse_article_heading(paragraph: str) -> tuple[int | None, str] | None:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if len(lines) != 1:
            return None
        line = lines[0]
        if line.startswith("#"):
            marker, _, text = line.partition(" ")
            if marker and set(marker) == {"#"} and text.strip():
                return min(len(marker), 6), text.strip()
        if len(line) <= 120:
            number, separator, text = line.partition(". ")
            if separator and number.replace(".", "").isdigit() and text.strip():
                return None, line
        return None

    @staticmethod
    def _infer_article_block_type(text: str) -> str:
        stripped = text.strip()
        lines = [line for line in stripped.splitlines() if line.strip()]
        if stripped.startswith("```"):
            return "code"
        if len(lines) >= 2 and all(line.strip().startswith("|") for line in lines[:2]):
            return "table"
        list_markers = ("- ", "* ", "• ")
        numbered_count = 0
        list_count = 0
        for line in lines:
            compact = line.strip()
            if compact.startswith(list_markers):
                list_count += 1
                continue
            first, separator, _ = compact.partition(". ")
            if separator and first.isdigit():
                numbered_count += 1
        if lines and (list_count + numbered_count) / len(lines) >= 0.5:
            return "list"
        return "text"

    def _merge_small_article_sections(
        self,
        leaves: list[_ArticleLeafSection],
        *,
        max_chars: int,
    ) -> list[_ArticleLeafSection]:
        # 작은 section 병합 단계: 너무 짧은 section은 같은 parent 아래의 다음 section과 합쳐
        # 검색 chunk가 과도하게 잘게 쪼개지는 것을 막는다.
        if len(leaves) <= 1:
            return leaves

        merged: list[_ArticleLeafSection] = []
        i = 0
        while i < len(leaves):
            current = leaves[i]
            current_len = self._calc_article_leaf_length(current)
            if current_len >= ARTICLE_CHUNK_MIN_CHARS:
                merged.append(current)
                i += 1
                continue

            if i + 1 < len(leaves):
                next_leaf = leaves[i + 1]
                next_len = self._calc_article_leaf_length(next_leaf)
                if (
                    current.parent_key == next_leaf.parent_key
                    and current_len + next_len <= max_chars
                ):
                    leaves[i + 1] = _ArticleLeafSection(
                        hierarchy=current.hierarchy,
                        content_blocks=self._append_article_section_blocks(
                            base=current,
                            appended=next_leaf,
                        ),
                        parent_key=current.parent_key,
                    )
                    i += 1
                    continue

            merged.append(current)
            i += 1

        return merged

    def _split_large_article_sections(
        self,
        leaves: list[_ArticleLeafSection],
        *,
        target_chars: int,
        max_chars: int,
    ) -> list[_ArticleLeafSection]:
        # 큰 section 분할 단계: target size를 넘는 leaf만 block 단위로 나눠
        # table/list/code 같은 구조가 가능한 한 유지되도록 한다.
        result: list[_ArticleLeafSection] = []
        for leaf in leaves:
            if self._calc_article_leaf_length(leaf) <= target_chars:
                result.append(leaf)
                continue
            result.extend(
                self._split_article_leaf(
                    leaf,
                    target_chars=target_chars,
                    max_chars=max_chars,
                )
            )
        return result

    def _split_article_leaf(
        self,
        leaf: _ArticleLeafSection,
        *,
        target_chars: int,
        max_chars: int,
    ) -> list[_ArticleLeafSection]:
        split_result: list[_ArticleLeafSection] = []
        current_blocks: list[_ArticleContentBlock] = []
        current_len = 0

        def emit_current() -> None:
            nonlocal current_blocks, current_len
            if not current_blocks:
                return
            split_result.append(
                _ArticleLeafSection(
                    hierarchy=list(leaf.hierarchy),
                    content_blocks=current_blocks,
                    parent_key=leaf.parent_key,
                )
            )
            current_blocks = []
            current_len = 0

        for block in leaf.content_blocks:
            block_len = len(block.text)
            if block_len > max_chars:
                emit_current()
                for sub_block in self._split_oversized_article_block(
                    block,
                    max_chars=max_chars,
                ):
                    split_result.append(
                        _ArticleLeafSection(
                            hierarchy=list(leaf.hierarchy),
                            content_blocks=[sub_block],
                            parent_key=leaf.parent_key,
                        )
                    )
                continue

            if current_blocks and current_len + block_len > target_chars:
                emit_current()

            current_blocks.append(block)
            current_len += block_len

        emit_current()
        return split_result

    def _split_oversized_article_block(
        self,
        block: _ArticleContentBlock,
        *,
        max_chars: int,
    ) -> list[_ArticleContentBlock]:
        if block.block_type == "table":
            return self._split_table_article_block(block, max_chars=max_chars)
        if block.block_type == "list":
            return self._split_list_article_block(block, max_chars=max_chars)
        if block.block_type == "code":
            return [block]
        return self._split_text_article_block(block, max_chars=max_chars)

    @staticmethod
    def _split_table_article_block(
        block: _ArticleContentBlock,
        *,
        max_chars: int,
    ) -> list[_ArticleContentBlock]:
        lines = block.text.splitlines()
        if len(lines) < 3:
            return [block]
        header_lines = lines[:2]
        data_lines = lines[2:]
        header_text = "\n".join(header_lines)
        result: list[_ArticleContentBlock] = []
        current_data: list[str] = []
        current_len = len(header_text)

        for data_line in data_lines:
            line_len = len(data_line) + 1
            if current_data and current_len + line_len > max_chars:
                result.append(
                    _ArticleContentBlock(
                        block_type="table",
                        text=f"{header_text}\n" + "\n".join(current_data),
                    )
                )
                current_data = []
                current_len = len(header_text)
            current_data.append(data_line)
            current_len += line_len

        if current_data:
            result.append(
                _ArticleContentBlock(
                    block_type="table",
                    text=f"{header_text}\n" + "\n".join(current_data),
                )
            )
        return result or [block]

    @staticmethod
    def _split_list_article_block(
        block: _ArticleContentBlock,
        *,
        max_chars: int,
    ) -> list[_ArticleContentBlock]:
        groups: list[list[str]] = []
        current_group: list[str] = []
        for line in block.text.splitlines():
            stripped = line.strip()
            is_top_level = bool(stripped) and line == line.lstrip()
            if is_top_level and current_group:
                groups.append(current_group)
                current_group = [line]
                continue
            current_group.append(line)
        if current_group:
            groups.append(current_group)

        result: list[_ArticleContentBlock] = []
        current_lines: list[str] = []
        current_len = 0
        for group in groups:
            group_len = len("\n".join(group))
            if current_lines and current_len + group_len > max_chars:
                result.append(
                    _ArticleContentBlock(
                        block_type="list",
                        text="\n".join(current_lines),
                    )
                )
                current_lines = []
                current_len = 0
            current_lines.extend(group)
            current_len += group_len
        if current_lines:
            result.append(
                _ArticleContentBlock(
                    block_type="list",
                    text="\n".join(current_lines),
                )
            )
        return result or [block]

    @staticmethod
    def _split_text_article_block(
        block: _ArticleContentBlock,
        *,
        max_chars: int,
    ) -> list[_ArticleContentBlock]:
        result: list[_ArticleContentBlock] = []
        current_lines: list[str] = []
        current_len = 0
        for line in block.text.splitlines() or [block.text]:
            if len(line) > max_chars:
                if current_lines:
                    result.append(
                        _ArticleContentBlock(
                            block_type="text",
                            text="\n".join(current_lines),
                        )
                    )
                    current_lines = []
                    current_len = 0
                result.extend(
                    _ArticleContentBlock(
                        block_type="text",
                        text=line[index : index + max_chars].strip(),
                    )
                    for index in range(0, len(line), max_chars)
                    if line[index : index + max_chars].strip()
                )
                continue

            line_len = len(line) + 1
            if current_lines and current_len + line_len > max_chars:
                result.append(
                    _ArticleContentBlock(
                        block_type="text",
                        text="\n".join(current_lines),
                    )
                )
                current_lines = []
                current_len = 0
            current_lines.append(line)
            current_len += line_len

        if current_lines:
            result.append(
                _ArticleContentBlock(
                    block_type="text",
                    text="\n".join(current_lines),
                )
            )
        return result or [block]

    def _merge_post_split_article_sections(
        self,
        leaves: list[_ArticleLeafSection],
        *,
        max_chars: int,
    ) -> list[_ArticleLeafSection]:
        # 후처리 병합 단계: split 이후 생긴 짧은 tail section을 이웃과 다시 합쳐
        # chunk 품질을 안정화한다.
        if len(leaves) <= 1:
            return leaves

        result = list(leaves)
        i = 0
        while i < len(result):
            current = result[i]
            if self._calc_article_leaf_length(current) >= ARTICLE_CHUNK_MIN_CHARS:
                i += 1
                continue

            prev = result[i - 1] if i > 0 else None
            next_leaf = result[i + 1] if i + 1 < len(result) else None
            direction = self._choose_article_merge_direction(
                prev=prev,
                current=current,
                next_leaf=next_leaf,
                max_chars=max_chars,
            )
            if direction is None:
                i += 1
                continue

            if direction == "prev" and prev is not None:
                result[i - 1] = _ArticleLeafSection(
                    hierarchy=prev.hierarchy,
                    content_blocks=self._append_article_section_blocks(
                        base=prev,
                        appended=current,
                    ),
                    parent_key=prev.parent_key,
                )
                result.pop(i)
                continue

            if direction == "next" and next_leaf is not None:
                result[i] = _ArticleLeafSection(
                    hierarchy=next_leaf.hierarchy,
                    content_blocks=self._append_article_section_blocks(
                        base=current,
                        appended=next_leaf,
                    ),
                    parent_key=next_leaf.parent_key,
                )
                result.pop(i + 1)
                continue

            i += 1

        return result

    def _choose_article_merge_direction(
        self,
        *,
        prev: _ArticleLeafSection | None,
        current: _ArticleLeafSection,
        next_leaf: _ArticleLeafSection | None,
        max_chars: int,
    ) -> str | None:
        candidates: list[tuple[str, _ArticleLeafSection]] = []
        current_len = self._calc_article_leaf_length(current)
        if (
            prev is not None
            and prev.hierarchy == current.hierarchy
            and current_len + self._calc_article_leaf_length(prev) <= max_chars
        ):
            candidates.append(("prev", prev))
        if (
            next_leaf is not None
            and next_leaf.hierarchy == current.hierarchy
            and current_len + self._calc_article_leaf_length(next_leaf) <= max_chars
        ):
            candidates.append(("next", next_leaf))
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0][0]

        prev_leaf = candidates[0][1]
        next_candidate = candidates[1][1]
        prev_prefix = self._common_prefix_len(current.hierarchy, prev_leaf.hierarchy)
        next_prefix = self._common_prefix_len(
            current.hierarchy,
            next_candidate.hierarchy,
        )
        if prev_prefix != next_prefix:
            return "prev" if prev_prefix > next_prefix else "next"

        prev_len = self._calc_article_leaf_length(prev_leaf)
        next_len = self._calc_article_leaf_length(next_candidate)
        return "prev" if prev_len <= next_len else "next"

    def _append_article_section_blocks(
        self,
        *,
        base: _ArticleLeafSection,
        appended: _ArticleLeafSection,
    ) -> list[_ArticleContentBlock]:
        appended_heading = self._build_embedded_article_section_heading(
            base_hierarchy=base.hierarchy,
            appended_hierarchy=appended.hierarchy,
        )
        if appended_heading is None:
            return base.content_blocks + appended.content_blocks
        return [
            *base.content_blocks,
            _ArticleContentBlock(block_type="heading", text=appended_heading),
            *appended.content_blocks,
        ]

    @staticmethod
    def _build_embedded_article_section_heading(
        *,
        base_hierarchy: list[str],
        appended_hierarchy: list[str],
    ) -> str | None:
        if not appended_hierarchy or appended_hierarchy == base_hierarchy:
            return None

        common_prefix_len = 0
        for base_item, appended_item in zip(base_hierarchy, appended_hierarchy):
            if base_item != appended_item:
                break
            common_prefix_len += 1

        heading_parts = appended_hierarchy[common_prefix_len:]
        if not heading_parts:
            return None
        return " > ".join(heading_parts)

    def _build_article_chunks(
        self,
        *,
        header: str,
        leaves: list[_ArticleLeafSection],
    ) -> list[str]:
        # 최종 chunk 생성 단계: article title과 section path를 heading으로 붙여
        # 개별 chunk만 봐도 원문 내 위치를 알 수 있게 한다.
        chunks: list[str] = []
        for leaf in leaves:
            body = "\n\n".join(
                block.text for block in leaf.content_blocks if block.text
            ).strip()
            content_parts = []
            chunk_heading = self._build_article_chunk_heading(header, leaf.hierarchy)
            if chunk_heading:
                content_parts.append(chunk_heading)
            if body:
                content_parts.append(body)
            chunks.append("\n\n".join(content_parts).strip())
        return chunks

    @staticmethod
    def _build_article_chunk_heading(article_title: str, hierarchy: list[str]) -> str:
        title = article_title.strip()
        section_hierarchy = list(hierarchy)
        if title and section_hierarchy:
            normalized_title = " ".join(title.split())
            first_section = " ".join(section_hierarchy[0].split())
            if normalized_title == first_section:
                section_hierarchy = section_hierarchy[1:]
        section_path = " > ".join(section_hierarchy)
        if title and section_path:
            return f"{title} - {section_path}"
        return title or section_path

    @staticmethod
    def _calc_article_leaf_length(leaf: _ArticleLeafSection) -> int:
        return sum(len(block.text or "") for block in leaf.content_blocks)

    @staticmethod
    def _common_prefix_len(left: list[str], right: list[str]) -> int:
        count = 0
        for left_item, right_item in zip(left, right):
            if left_item != right_item:
                break
            count += 1
        return count

    @staticmethod
    def _split_paragraphs(body: str) -> tuple[str, ...]:
        if not body:
            return ()
        paragraphs = [
            paragraph.strip()
            for paragraph in body.replace("\r\n", "\n").split("\n\n")
            if paragraph.strip()
        ]
        if paragraphs:
            return tuple(paragraphs)
        return tuple(line.strip() for line in body.splitlines() if line.strip())
