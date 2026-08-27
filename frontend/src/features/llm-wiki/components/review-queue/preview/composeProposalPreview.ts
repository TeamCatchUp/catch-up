/** 검토 중인 변경안 + 블록 판정 → 문서 화면에 그릴 항목. 순수 함수라 요청·캐시를 알지 못한다. */

import type { ReviewProposalDetailData } from '../../../api/knowledgeReviewDetailMappers';
import type { WikiBlock } from '../../../types/llmWikiDiff';
import {
  composeDocumentPresentation,
  type DocumentPresentationBlock,
  type DocumentPresentationItem,
} from '../../document/composeDocumentPresentation';

export type ProposalPreviewItem = DocumentPresentationItem;

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
    return composeDocumentPresentation(
      blocks.flatMap((block) =>
        block
          ? [{ blockIndex: block.blockIndex, kind: block.kind, heading: block.heading, text: displayText(block) }]
          : [],
      ),
    );
  }

  const presentationBlocks: DocumentPresentationBlock[] = detail.layout.flatMap((item) => {
    if (item.kind === 'placeholder') return [{ blockIndex: -1, kind: 'placeholder', heading: item.heading, text: item.text }];
    const block = blocks[item.blockIndex];
    return block
      ? [{ blockIndex: block.blockIndex, kind: block.kind, heading: item.heading, text: displayText(block) }]
      : [];
  });

  return composeDocumentPresentation(presentationBlocks);
}
