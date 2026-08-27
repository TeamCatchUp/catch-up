import { Diff } from 'diff';

import type { WikiLayoutItem } from '../../api/wikiDocumentMappers';
import type { BlockChange, BlockDiffEntry, DiffLine, DiffSegment, WikiBlock } from '../../types/llmWikiDiff';

interface ChangePart {
  value: string;
  added?: boolean;
  removed?: boolean;
}

/**
 * 공백 토큰화 단어 diff. jsdiff 기본 토크나이저는 유니코드 단어 경계로 나눠
 * 숫자↔한글 사이가 쪼개지므로("1회" → "1"+"회") tokenizer를 직접 지정한다.
 */
const wordDiff = new Diff<string, string>();
wordDiff.tokenize = (value: string) => value.split(/(\s+)/).filter((token) => token.length > 0);

/** diff 파트 목록을 한쪽(before/after) 줄 목록으로 접는다. 줄바꿈이 DiffLine 경계다 */
function toLines(parts: readonly ChangePart[], side: 'before' | 'after'): DiffLine[] {
  const lines: DiffSegment[][] = [[]];
  for (const part of parts) {
    if (side === 'before' && part.added) continue;
    if (side === 'after' && part.removed) continue;
    const emphasized = side === 'before' ? Boolean(part.removed) : Boolean(part.added);
    part.value.split('\n').forEach((chunk, index) => {
      if (index > 0) lines.push([]);
      if (chunk.length > 0) lines[lines.length - 1].push({ text: chunk, emphasized });
    });
  }
  return lines.map((segments) => ({ segments }));
}

/** added·removed 카드용 — 강조 없는 줄 목록. 패널 색이 변경 표시의 전부다 */
function plainLines(body: string): DiffLine[] {
  return body.split('\n').map((text) => ({ segments: text.length > 0 ? [{ text, emphasized: false }] : [] }));
}

/** 화면에 실리는 본문. 산문이 정본이고 없으면 값 표기로 폴백한다 */
const displayBody = (block: WikiBlock) => block.narrative ?? block.body;

/** 좌우 비교는 한 축에서만 한다 — 한쪽만 산문이면 축이 섞여 전부 바뀐 것처럼 보인다 */
function comparedPair(base: WikiBlock, proposed: WikiBlock): [string, string] {
  return base.narrative != null && proposed.narrative != null
    ? [base.narrative, proposed.narrative]
    : [base.body, proposed.body];
}

/** 판정 요청에 필요한 값과 저장된 판정. 판정된 카드는 접히고 액션이 빠진다 */
function verdictFields(proposed: WikiBlock) {
  return {
    blockIndex: proposed.blockIndex,
    blockContentHash: proposed.blockContentHash,
    rejected: proposed.verdict?.verdict === 'rejected',
    approved: proposed.verdict?.verdict === 'approved',
    rejectionReason: proposed.verdict?.rejectionReason ?? null,
  };
}

/** 양식이 블록 하나에 준 자리와 이름. 표로 묶인 블록은 그 행 이름이 블록 이름이다 */
interface LayoutSlot {
  position: number;
  label?: string;
}

function indexLayoutSlots(layout: readonly WikiLayoutItem[]): Map<number, LayoutSlot> {
  const slots = new Map<number, LayoutSlot>();

  layout.forEach((item, position) => {
    if (item.kind === 'block') slots.set(item.blockIndex, { position, label: item.heading });
  });

  return slots;
}

/**
 * 카드 순서만 양식 순서로 바꾼다. 자리에 이름이 없는 카드(빠진 블록)는 원래 순서대로 뒤에 남는다.
 * 판정에 쓰는 blockIndex·blockContentHash는 카드가 그대로 들고 있어 재배치와 무관하다.
 */
function sortByLayout(entries: readonly BlockDiffEntry[], slots: ReadonlyMap<number, LayoutSlot>): BlockDiffEntry[] {
  const rank = (entry: BlockDiffEntry) =>
    (entry.blockIndex === null ? undefined : slots.get(entry.blockIndex)?.position) ?? Number.MAX_SAFE_INTEGER;

  return [...entries].sort((left, right) => rank(left) - rank(right));
}

/**
 * 서버가 계산한 변경 목록을 diff 카드로 옮긴다. 짝짓기는 하지 않고 자리만 따라간다 —
 * 같은 안건이 소비자마다 다르게 보이지 않으려면 짝짓기 규칙이 한 곳에만 있어야 한다.
 * 자리가 blocks 범위를 벗어난 변경은 카드를 만들지 않는다.
 */
export function buildBlockDiff(
  baseBlocks: readonly WikiBlock[],
  proposedBlocks: readonly WikiBlock[],
  changes: readonly BlockChange[],
  /** 있으면 카드 순서가 이 양식을 따른다. 비면 서버 변경 목록 순서 그대로다 */
  layout: readonly WikiLayoutItem[] = [],
): BlockDiffEntry[] {
  const entries: BlockDiffEntry[] = [];
  const slots = indexLayoutSlots(layout);
  // 카드 제목은 양식이 붙인 사람용 이름이다 — 이름이 없는 자리만 블록 heading으로 남는다
  const titleOf = (block: WikiBlock) => slots.get(block.blockIndex)?.label ?? block.heading;

  for (const change of changes) {
    const base = change.baseBlockIndex === null ? undefined : baseBlocks[change.baseBlockIndex];
    const proposed = change.blockIndex === null ? undefined : proposedBlocks[change.blockIndex];

    if (change.kind === 'removed') {
      // 변경안에 자리가 없어 사유도 판정 경로도 없다 — 발행판 원문만 보여 준다
      if (!base) continue;
      entries.push({
        id: `removed-${change.baseBlockIndex}`,
        kind: 'removed',
        title: base.heading,
        before: plainLines(displayBody(base)),
        after: null,
        reason: null,
        blockIndex: null,
        blockContentHash: null,
      });
      continue;
    }

    if (!proposed) continue;

    if (change.kind === 'added') {
      entries.push({
        id: `added-${change.blockIndex}`,
        kind: 'added',
        title: titleOf(proposed),
        before: null,
        after: plainLines(displayBody(proposed)),
        reason: proposed.reason ?? null,
        ...verdictFields(proposed),
      });
      continue;
    }

    if (!base) continue;
    // 강조는 화면에 실린 본문 축에서만 낸다 — 변경 판정 자체는 서버가 이미 했다
    const parts = wordDiff.diff(...comparedPair(base, proposed));
    entries.push({
      id: `modified-${change.blockIndex}`,
      kind: 'modified',
      title: titleOf(proposed),
      before: toLines(parts, 'before'),
      after: toLines(parts, 'after'),
      reason: proposed.reason ?? null,
      ...verdictFields(proposed),
    });
  }

  return layout.length > 0 ? sortByLayout(entries, slots) : entries;
}
