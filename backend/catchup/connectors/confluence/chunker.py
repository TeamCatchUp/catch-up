"""
Confluence Section Tree -> Semantic Chunk

1. Leaf Flattening       : Section tree → LeafSection 리스트로 평탄화
2. 1차 병합 (MIN 기준)   : 같은 parent에서 작은 leaf를 다음 형제로 흡수
3. 1차 분할 (MAX 기준)   : 큰 leaf를 ContentBlock 경계에서 분할
4. 2차 병합 (split 후처리): split에서 생긴 MIN 미만 조각을 인접 leaf로 병합
5. 최종 Chunk 생성       : Context Prefix + 텍스트 합치기

- TARGET_CHARS = 2000  (~500 tokens)
- MAX_CHARS    = 4000  (~1000 tokens)
- MIN_CHARS    = 400   (~100 tokens)
"""

import logging
from dataclasses import dataclass
from dataclasses import field

from catchup.connectors.confluence.storage_parser import ContentBlock
from catchup.connectors.confluence.storage_parser import Section

logger = logging.getLogger(__name__)

# 청킹 크기 상수
TARGET_CHARS = 2000   # ~500 tokens
MAX_CHARS = 4000      # ~1000 tokens
MIN_CHARS = 400       # ~100 tokens

@dataclass
class LeafSection:
    """
    Flattened Leaf Node

    Attributes:
        hierarchy: 상위 heading
        content_blocks: Content Block List
        parent_key
    """

    hierarchy: list[str]
    content_blocks: list[ContentBlock]
    parent_key: str


@dataclass
class Chunk:
    """
    최종 Chunk

    transformers.py에서 LangChain Document로 변환할 때 사용.

    Attributes:
        index: 이 페이지 내에서의 chunk 순번 (0부터)
        content: context prefix 포함된 최종 텍스트 (Document.page_content)
        section_hierarchy: heading 경로 (metadata에 저장)
        char_count: content의 문자 수
        estimated_tokens: 추정 토큰 수 (문자수 // 4)
        image_blocks: 이 chunk에 포함된 이미지 ContentBlock들
                      (transformers.py에서 Attachment 다운로드 + base64 변환에 사용)
    """

    index: int
    content: str
    section_hierarchy: list[str]
    char_count: int
    estimated_tokens: int
    image_blocks: list[ContentBlock] = field(default_factory=list)
    inline_comment_refs: list[str] = field(default_factory=list)
    body_text: str = ""


class ConfluenceChunker:
    """
    Section Tree → Chunk List
    """

    _SPECIAL_TYPES = frozenset({"code", "table", "list"})

    def __init__(
        self,
        target_chars: int = TARGET_CHARS,
        max_chars: int = MAX_CHARS,
        min_chars: int = MIN_CHARS,
    ):
        self.target_chars = target_chars
        self.max_chars = max_chars
        self.min_chars = min_chars

    def chunk(self, sections: list[Section], page_title: str) -> list[Chunk]:
        if not sections:
            return []

        # Step 1: Leaf Section Flattening
        leaves = self._flatten_leaf_sections(sections, parent_hierarchy=[])

        if not leaves:
            return []

        # Step 2: Merge Small Sections
        merged = self._merge_small_sections(leaves)

        # Step 3: Split Large Sections
        split = self._split_large_sections(merged)

        post_merged = self._merge_post_split(split)

        # Step 4: Context Prefix + 최종 Chunk 생성
        chunks = self._build_chunks(post_merged, page_title)

        return chunks

    # ================================================================
    # Step 1: 리프 섹션 플래트닝
    # ================================================================

    def _flatten_leaf_sections(
        self,
        sections: list[Section],
        parent_hierarchy: list[str],
    ) -> list[LeafSection]:

        leaves: list[LeafSection] = []

        for section in sections:
            current_hierarchy = parent_hierarchy.copy()
            if section.heading_text:
                current_hierarchy.append(section.heading_text)

            parent_key = " > ".join(parent_hierarchy)

            if section.children:
                # 자식이 있는 Section에 content_blocks가 있으면 별도 리프로 추출
                if section.content_blocks:
                    leaves.append(LeafSection(
                        hierarchy=current_hierarchy,
                        content_blocks=section.content_blocks,
                        parent_key=parent_key,
                    ))

                # Children Section을 재귀 탐색
                leaves.extend(
                    self._flatten_leaf_sections(section.children, current_hierarchy)
                )
            else:
                # 리프 노드
                if section.content_blocks:
                    leaves.append(LeafSection(
                        hierarchy=current_hierarchy,
                        content_blocks=section.content_blocks,
                        parent_key=parent_key,
                    ))
                elif section.heading_text:
                    # Heading만 있는 섹션 -> 별도의 Content Block으로 추출
                    leaves.append(LeafSection(
                        hierarchy=current_hierarchy,
                        content_blocks=[ContentBlock(
                            block_type="text",
                            text=section.heading_text,
                        )],
                        parent_key=parent_key,
                    ))

        return leaves

    # ================================================================
    # Step 2: 소형 섹션 병합
    # ================================================================

    def _merge_small_sections(self, leaves: list[LeafSection]) -> list[LeafSection]:
        """
        MIN_CHARS 미만인 작은 리프 섹션을 같은 부모의 다음 형제와 병합

        [병합 규칙]
        1. 현재 리프의 텍스트가 MIN_CHARS 미만이면 다음 리프와 병합 시도
        2. 다음 리프가 같은 parent_key를 가져야 병합
        3. 병합 결과가 MAX_CHARS를 초과하면 병합하지 않음
        4. 병합 시 hierarchy는 첫 번째 리프의 것을 사용
        """
        if len(leaves) <= 1:
            return leaves

        merged: list[LeafSection] = []
        i = 0

        while i < len(leaves):
            current = leaves[i]
            current_len = self._calc_leaf_length(current)

            if current_len >= self.min_chars:
                merged.append(current)
                i += 1
                continue

            if i + 1 < len(leaves):
                next_leaf = leaves[i + 1]
                next_len = self._calc_leaf_length(next_leaf)

                if (
                    current.parent_key == next_leaf.parent_key
                    and current_len + next_len <= self.max_chars
                ):
                    merged_leaf = LeafSection(
                        hierarchy=current.hierarchy,
                        content_blocks=current.content_blocks + next_leaf.content_blocks,
                        parent_key=current.parent_key,
                    )
                    leaves[i + 1] = merged_leaf
                    i += 1
                    continue

            merged.append(current)
            i += 1

        return merged

    # ================================================================
    # Step 3: 대형 섹션 분할
    # ================================================================

    def _split_large_sections(self, leaves: list[LeafSection]) -> list[LeafSection]:
        """
        MAX_CHARS 초과하는 큰 리프 섹션을 ContentBlock 경계에서 분할

        [분할 규칙]
        1. ContentBlock 단위로 분할
        2. 특수 블록(table, code, list)은 중간에서 분할하지 않음
        """
        result: list[LeafSection] = []

        for leaf in leaves:
            leaf_len = self._calc_leaf_length(leaf)

            if leaf_len <= self.max_chars:
                result.append(leaf)
                continue

            # MAX_CHARS 초과 → 분할
            split_leaves = self._split_leaf(leaf)
            result.extend(split_leaves)

        return result

    def _split_leaf(self, leaf: LeafSection) -> list[LeafSection]:
        """
        단일 리프를 ContentBlock 경계에서 분할

        블록을 순서대로 현재 청크에 넣다가,
        MAX_CHARS를 초과하면 새 청크를 시작한다.
        """
        split_result: list[LeafSection] = []
        current_blocks: list[ContentBlock] = []
        current_len = 0

        for block in leaf.content_blocks:
            block_len = len(block.text)

            # 특수 블록이 단독으로 MAX_CHARS 초과하는 경우 → 내부 분할
            if block_len > self.max_chars:
                # 현재까지 모은 블록이 있으면 먼저 확정
                if current_blocks:
                    split_result.append(LeafSection(
                        hierarchy=leaf.hierarchy,
                        content_blocks=current_blocks,
                        parent_key=leaf.parent_key,
                    ))
                    current_blocks = []
                    current_len = 0

                # 특수 블록 내부 분할
                sub_blocks = self._split_oversized_block(block)
                for sub in sub_blocks:
                    split_result.append(LeafSection(
                        hierarchy=leaf.hierarchy,
                        content_blocks=[sub],
                        parent_key=leaf.parent_key,
                    ))
                continue

            # 현재 청크에 이 블록을 추가하면 MAX_CHARS 초과? → 새 청크 시작
            if current_len + block_len > self.max_chars and current_blocks:
                split_result.append(LeafSection(
                    hierarchy=leaf.hierarchy,
                    content_blocks=current_blocks,
                    parent_key=leaf.parent_key,
                ))
                current_blocks = []
                current_len = 0

            current_blocks.append(block)
            current_len += block_len

        # 남은 블록 처리
        if current_blocks:
            split_result.append(LeafSection(
                hierarchy=leaf.hierarchy,
                content_blocks=current_blocks,
                parent_key=leaf.parent_key,
            ))

        return split_result

    def _split_oversized_block(self, block: ContentBlock) -> list[ContentBlock]:
        """
        MAX_CHARS를 초과하는 단일 블록의 내부 분할

        블록 타입에 따라 분할 전략이 다름:
        - table: 헤더행 반복 + N개 데이터행 단위
        - code: 그대로 별도 블록
        - list: 최상위 아이템 단위
        - text: 줄바꿈 경계에서 분할
        """
        if block.block_type == "table":
            return self._split_table_block(block)
        elif block.block_type == "list":
            return self._split_list_block(block)
        elif block.block_type == "code":
            # 코드블록은 더 이상 쪼개지 않음 (의미 훼손 방지)
            return [block]
        else:
            # text 등: 줄바꿈 경계에서 분할
            return self._split_text_block(block)

    def _split_table_block(self, block: ContentBlock) -> list[ContentBlock]:
        """
        테이블 분할: 헤더행을 각 분할 조각에 반복 포함

        입력:
            | Col A | Col B |    ← 헤더
            | --- | --- |        ← 구분선
            | D1 | D2 |         ← 데이터
            | D3 | D4 |
            ...

        출력 (2개 분할 시):
            조각1: 헤더 + 구분선 + 데이터 일부
            조각2: 헤더 + 구분선 + 나머지 데이터
        """
        lines = block.text.split("\n")
        if len(lines) < 3:
            return [block]

        # 첫 2줄 = 헤더 + 구분선
        header_lines = lines[:2]
        data_lines = lines[2:]
        header_text = "\n".join(header_lines)
        header_len = len(header_text)

        result: list[ContentBlock] = []
        current_data: list[str] = []
        current_len = header_len

        for data_line in data_lines:
            line_len = len(data_line) + 1  # +1 for \n

            if current_len + line_len > self.max_chars and current_data:
                # 현재 조각 확정 (헤더 + 데이터)
                chunk_text = header_text + "\n" + "\n".join(current_data)
                result.append(ContentBlock(block_type="table", text=chunk_text))
                current_data = []
                current_len = header_len

            current_data.append(data_line)
            current_len += line_len

        # 남은 데이터
        if current_data:
            chunk_text = header_text + "\n" + "\n".join(current_data)
            result.append(ContentBlock(block_type="table", text=chunk_text))

        return result if result else [block]

    def _split_list_block(self, block: ContentBlock) -> list[ContentBlock]:
        """
        리스트 분할: 최상위 아이템(들여쓰기 없는 라인) 단위로 분할

        최상위 아이템과 그 하위 아이템(들여쓰기된 라인)을 하나의 그룹으로 묶어서
        MAX_CHARS를 초과하면 새 그룹을 시작한다.
        """
        lines = block.text.split("\n")

        # 최상위 아이템 그룹 분리
        # 들여쓰기가 없는 라인이 새 최상위 아이템의 시작
        groups: list[list[str]] = []
        current_group: list[str] = []

        for line in lines:
            if line and not line.startswith(" ") and not line.startswith("\t"):
                # 새 최상위 아이템 시작
                if current_group:
                    groups.append(current_group)
                current_group = [line]
            else:
                # 하위 아이템 (들여쓰기) → 현재 그룹에 추가
                current_group.append(line)

        if current_group:
            groups.append(current_group)

        # 그룹들을 MAX_CHARS 기준으로 청킹
        result: list[ContentBlock] = []
        current_lines: list[str] = []
        current_len = 0

        for group in groups:
            group_text = "\n".join(group)
            group_len = len(group_text)

            if current_len + group_len > self.max_chars and current_lines:
                result.append(ContentBlock(
                    block_type="list",
                    text="\n".join(current_lines),
                ))
                current_lines = []
                current_len = 0

            current_lines.extend(group)
            current_len += group_len

        if current_lines:
            result.append(ContentBlock(
                block_type="list",
                text="\n".join(current_lines),
            ))

        return result if result else [block]

    def _split_text_block(self, block: ContentBlock) -> list[ContentBlock]:
        """텍스트 블록을 줄바꿈 경계에서 분할"""
        lines = block.text.split("\n")
        result: list[ContentBlock] = []
        current_lines: list[str] = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1  # +1 for \n

            if current_len + line_len > self.max_chars and current_lines:
                result.append(ContentBlock(
                    block_type="text",
                    text="\n".join(current_lines),
                ))
                current_lines = []
                current_len = 0

            current_lines.append(line)
            current_len += line_len

        if current_lines:
            result.append(ContentBlock(
                block_type="text",
                text="\n".join(current_lines),
            ))

        return result if result else [block]
    
    # ================================================================
    # Step 3.5: Split 이후 2차 병합
    # ================================================================

    def _merge_post_split(self, leaves: list[LeafSection]) -> list[LeafSection]:
        if len(leaves) <= 1:
            return leaves
        
        result: list[LeafSection] = list(leaves)
        i = 0

        while i < len(result):
            current = result[i]
            current_len = self._calc_leaf_length(current)

            if current_len >= self.min_chars:
                i += 1
                continue

            prev = result[i-1] if i>0 else None
            next_leaf = result[i+1] if i+1 < len(result) else None

            if prev is None and next_leaf is None:
                i += 1
                continue
            
            if prev is None:
                direction = "next"
            elif next_leaf is None:
                direction = "prev"
            else:
                direction = self._choose_merge_direction(prev, current, next_leaf)

            if direction == "prev":
                merged = LeafSection(
                    hierarchy= prev.hierarchy,
                    content_blocks = prev.content_blocks + current.content_blocks,
                    parent_key=prev.parent_key,
                )
                result[i - 1] = merged
                result.pop(i)
            else:
                merged = LeafSection(
                    hierarchy= next_leaf.hierarchy,
                    content_blocks = current.content_blocks + next_leaf.content_blocks,
                    parent_key = next_leaf.parent_key,
                )
                result[i] = merged
                result.pop(i + 1)
        
        return result
    
    def _choose_merge_direction(
            self,
            prev: LeafSection,
            current: LeafSection,
            next_leaf: LeafSection,
    ) -> str:
        cur_first = self._first_block_type(current)
        cur_last = self._last_block_type(current)
        prev_last = self._last_block_type(prev)
        next_first = self._first_block_type(next_leaf)

        # 1) 특수 블록 타입 경계 보존
        prev_match = (prev_last == cur_first) and (cur_first in self._SPECIAL_TYPES)
        next_match = (next_first == cur_last) and (cur_last in self._SPECIAL_TYPES)

        if prev_match and not next_match:
            return "prev"
        if next_match and not prev_match:
            return "next"
        if prev_match and next_match:
            return "prev"
        
        # 2) hiearchy Prefix 일치
        prev_prefix = self._common_prefix_len(current.hierarchy, prev.hierarchy)
        next_prefix = self._common_prefix_len(current.hierarchy, next_leaf.hierarchy)

        if prev_prefix > next_prefix:
            return "prev"
        if next_prefix > prev_prefix:
            return "next"

        # 3) 1,2 둘다 안되면 짧은 쪽으로 병합
        prev_len = self._calc_leaf_length(prev)
        next_len = self._calc_leaf_length(next_leaf)

        return "prev" if prev_len <= next_len else "next"

    @staticmethod
    def _first_block_type(leaf: LeafSection) -> str | None:
        if leaf.content_blocks:
            return leaf.content_blocks[0].block_type
        return None

    @staticmethod
    def _last_block_type(leaf: LeafSection) -> str | None:
        if leaf.content_blocks:
            return leaf.content_blocks[-1].block_type
        return None

    @staticmethod
    def _common_prefix_len(h1: list[str], h2: list[str]) -> int:
        count = 0
        for a, b in zip(h1, h2):
            if a == b:
                count += 1
            else:
                break
        return count


    # ================================================================
    # Step 4: 최종 Chunk 생성
    # ================================================================

    def _build_chunks(
        self, leaves: list[LeafSection], page_title: str
    ) -> list[Chunk]:
        """
        리프 섹션 리스트 → 최종 Chunk 리스트

        각 리프의 content_blocks를 텍스트로 합치고,
        Context Prefix를 붙여 최종 content를 생성한다.

        Context Prefix 형식:
            [Page: API 설계 가이드]
            [Section: 프로젝트 개요 > 기술 스택 > 백엔드]

            (chunk 본문)
        """
        chunks: list[Chunk] = []

        for idx, leaf in enumerate(leaves):
            # ContentBlock 텍스트를 합침
            body_parts: list[str] = []
            image_blocks: list[ContentBlock] = []
            comment_refs: list[str] = []

            for block in leaf.content_blocks:
                if block.text:
                    body_parts.append(block.text)
                # 이미지 블록은 별도 추적 (transformers.py에서 base64 변환에 사용)
                if block.block_type == "image":
                    image_blocks.append(block)
                if block.inline_comment_refs:
                    comment_refs.extend(block.inline_comment_refs)

            body = "\n\n".join(body_parts)

            # Context Prefix 생성
            prefix = self._build_context_prefix(page_title, leaf.hierarchy)
            content = f"{prefix}\n\n{body}" if prefix else body

            chunks.append(Chunk(
                index=idx,
                content=content,
                section_hierarchy=leaf.hierarchy,
                char_count=len(content),
                estimated_tokens=len(content) // 4,
                image_blocks=image_blocks,
                inline_comment_refs=comment_refs,
                body_text=body,
            ))

        return chunks

    def _build_context_prefix(
        self, page_title: str, hierarchy: list[str]
    ) -> str:
        """
        Chunk의 Context Prefix 생성

        이 prefix는 semantic_content(page_content)에 포함되어 임베딩됨.
        검색 시 "이 chunk가 어떤 페이지의 어떤 섹션인지"를 임베딩 공간에 반영한다.

        형식:
            [Page: API 설계 가이드]
            [Section: 인증 > OAuth 2.0]
        """
        parts: list[str] = []

        if page_title:
            parts.append(f"[Page: {page_title}]")

        if hierarchy:
            section_path = " > ".join(hierarchy)
            parts.append(f"[Section: {section_path}]")

        return "\n".join(parts)

    # ================================================================
    # 유틸리티
    # ================================================================

    def _calc_leaf_length(self, leaf: LeafSection) -> int:
        """리프 섹션의 총 텍스트 길이 계산"""
        return sum(len(block.text or "") for block in leaf.content_blocks)
