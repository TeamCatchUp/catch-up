import { Diff } from 'diff';

import type { BlockDiffEntry, DiffLine, DiffSegment, WikiBlock } from '../../types/llmWikiDiff';

interface ChangePart {
  value: string;
  added?: boolean;
  removed?: boolean;
}

/**
 * 공백 토큰화 단어 diff. jsdiff v9의 diffWordsWithSpace는 유니코드 단어 경계(UAX#29)로
 * 토큰을 나눠 숫자↔한글 사이가 쪼개진다("1회" → "1"+"회"). 스펙 §5가 공백 토큰화 기준이라
 * tokenizer를 직접 지정한다.
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
  return body
    .split('\n')
    .map((text) => ({ segments: text.length > 0 ? [{ text, emphasized: false }] : [] }));
}

const sharesClaimId = (a: WikiBlock, b: WikiBlock) => a.claimIds.some((id) => b.claimIds.includes(id));

/**
 * base/proposed blocks[]에서 diff 카드 목록을 만든다.
 *
 * 페어링은 claimIds 교집합 — 블록 고유 ID가 없어서다. 이 규칙은 백엔드 미문서화 상태의
 * [SPEC] 가정이므로, 계약이 확정되면 이 함수만 고친다. claimIds가 빈 블록은 페어링에
 * 실패해 added+removed 두 카드로 갈라진다(의도된 동작 — 테스트가 못박는다).
 */
export function computeBlockDiff(
  baseBlocks: readonly WikiBlock[],
  proposedBlocks: readonly WikiBlock[],
): BlockDiffEntry[] {
  const entries: BlockDiffEntry[] = [];
  const usedBase = new Set<number>();

  proposedBlocks.forEach((proposed, proposedIndex) => {
    const baseIndex = baseBlocks.findIndex(
      (candidate, index) => !usedBase.has(index) && sharesClaimId(candidate, proposed),
    );

    // 삭제 tombstone — 사유를 실으려고 proposed에 명시로 온다. 원문은 페어링된 base 쪽이다
    if (proposed.removed) {
      if (baseIndex !== -1) usedBase.add(baseIndex);
      const deleted = baseIndex === -1 ? proposed : baseBlocks[baseIndex];
      entries.push({
        id: `removed-${proposedIndex}`,
        kind: 'removed',
        title: deleted.heading,
        before: plainLines(deleted.body),
        after: null,
        reason: proposed.reason ?? null,
      });
      return;
    }

    if (baseIndex === -1) {
      entries.push({
        id: `added-${proposedIndex}`,
        kind: 'added',
        title: proposed.heading,
        before: null,
        after: plainLines(proposed.body),
        reason: proposed.reason ?? null,
      });
      return;
    }

    usedBase.add(baseIndex);
    const base = baseBlocks[baseIndex];
    if (base.body === proposed.body) return; // 변경 없음 — heading 변경 감지는 MVP 밖

    const parts = wordDiff.diff(base.body, proposed.body);
    entries.push({
      id: `modified-${proposedIndex}`,
      kind: 'modified',
      title: proposed.heading,
      before: toLines(parts, 'before'),
      after: toLines(parts, 'after'),
      reason: proposed.reason ?? null,
    });
  });

  // tombstone 없이 그냥 빠진 블록. 계약상 오면 안 되지만 조용히 사라지는 것보다 카드로 드러낸다 —
  // 사유를 실을 자리가 없어 reason은 null이고, 그 빈 푸터가 계약 위반의 표시가 된다
  baseBlocks.forEach((base, baseIndex) => {
    if (usedBase.has(baseIndex)) return;
    entries.push({
      id: `removed-orphan-${baseIndex}`,
      kind: 'removed',
      title: base.heading,
      before: plainLines(base.body),
      after: null,
      reason: null,
    });
  });

  return entries;
}
