/** 검토 중인 변경안 + 블록 판정 → 문서 화면에 그릴 항목. 순수 함수라 요청·캐시를 알지 못한다. */

import type { ReviewProposalDetailData } from '../../../api/knowledgeReviewDetailMappers';
import type { WikiLayoutRow } from '../../../api/wikiDocumentMappers';
import type { WikiBlock } from '../../../types/llmWikiDiff';

/** 문서 화면의 표시 항목 하나. 자리표시는 문구가 곧 본문이라 section으로 접는다 */
export type ProposalPreviewItem =
  | { kind: 'section'; heading: string; text: string }
  | { kind: 'table'; heading: string; rows: readonly WikiLayoutRow[] };

/** 화면에 실리는 본문. 산문이 정본이고 없으면 값 표기로 폴백한다 — diff 카드와 같은 규칙이다 */
const displayText = (block: WikiBlock) => block.narrative ?? block.body;

/** 변경안 자리 → 발행판 자리. 양쪽 짝이 있는 변경(modified)만 되돌릴 곳이 있다 */
function baseIndexByProposedIndex(detail: ReviewProposalDetailData): Map<number, number> {
  const map = new Map<number, number>();
  for (const change of detail.changes) {
    if (change.blockIndex !== null && change.baseBlockIndex !== null) {
      map.set(change.blockIndex, change.baseBlockIndex);
    }
  }
  return map;
}

/**
 * 판정을 반영한 블록 배열. 자리는 변경안 그대로라 layout의 blockIndex가 그대로 맞는다.
 * 승인·미판정은 제안 블록, 반려는 발행판 블록이고 되돌릴 자리가 없으면 null(제외)이다.
 */
function resolveBlocks(detail: ReviewProposalDetailData): (WikiBlock | null)[] {
  const baseIndex = baseIndexByProposedIndex(detail);

  return detail.blocks.map((block, index) => {
    if (block.verdict?.verdict !== 'rejected') return block;
    const at = baseIndex.get(index);
    return at === undefined ? null : (detail.baseBlocks[at] ?? null);
  });
}

/**
 * "지금 판정 그대로 발행하면 이렇게 된다"를 문서 화면 항목으로 조립한다.
 * 양식(layout)이 비면 블록 순서가 곧 표시 순서다 — 문서 화면과 같은 규칙이다.
 */
export function composeProposalPreview(detail: ReviewProposalDetailData): ProposalPreviewItem[] {
  const blocks = resolveBlocks(detail);

  if (detail.layout.length === 0) {
    return blocks.flatMap((block) =>
      block ? [{ kind: 'section' as const, heading: block.heading, text: displayText(block) }] : [],
    );
  }

  const items: ProposalPreviewItem[] = [];
  for (const item of detail.layout) {
    if (item.kind === 'placeholder') {
      items.push({ kind: 'section', heading: item.heading, text: item.text });
      continue;
    }

    if (item.kind === 'block') {
      const block = blocks[item.blockIndex];
      if (block) items.push({ kind: 'section', heading: item.heading, text: displayText(block) });
      continue;
    }

    // 표의 행과 블록 자리는 같은 순서로 짝지어 온다 — 빠진 블록의 행은 함께 빠진다
    const rows: WikiLayoutRow[] = [];
    item.blockIndexes.forEach((blockIndex, position) => {
      const block = blocks[blockIndex];
      const row = item.rows[position];
      if (block && row) rows.push({ label: row.label, value: displayText(block) });
    });
    if (rows.length > 0) items.push({ kind: 'table', heading: item.heading, rows });
  }

  return items;
}
