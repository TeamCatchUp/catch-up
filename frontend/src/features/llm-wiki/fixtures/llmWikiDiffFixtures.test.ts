import { describe, expect, it } from 'vitest';

import { buildBlockDiff } from '../utils/diff/buildBlockDiff';
import {
  BASE_WIKI_BLOCKS,
  CONTESTED_PROPOSED_BLOCKS,
  JUDGED_PROPOSED_BLOCKS,
  LONG_BASE_WIKI_BLOCKS,
  LONG_PROPOSED_WIKI_BLOCKS,
  PROPOSED_BLOCK_CHANGES,
  PROPOSED_WIKI_BLOCKS,
  PROPOSED_WIKI_LAYOUT,
  SINGLE_MODIFIED_BLOCK_CHANGES,
} from './llmWikiDiffFixtures';

/** DiffLine 목록을 한 문자열로 편다 — 어느 축의 본문이 실렸는지 보려는 용도다 */
const flatten = (lines: readonly { segments: readonly { text: string }[] }[] | null) =>
  (lines ?? []).map((line) => line.segments.map((segment) => segment.text).join('')).join('\n');

describe('llmWikiDiffFixtures', () => {
  it('기본 쌍은 modified → added → removed 세 카드를 낸다 (스토리 계약)', () => {
    const entries = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);
    expect(entries.map((e) => e.kind)).toEqual(['modified', 'added', 'removed']);
    expect(entries.map((e) => e.title)).toEqual(['재시도 정책', 'PG 점검 시간 예외', '수동 재시도 안내']);
  });

  it('양식을 함께 주면 카드 순서만 바뀐다 — 카드 구성은 그대로다', () => {
    const plain = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);
    const laid = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES, PROPOSED_WIKI_LAYOUT);

    expect(laid.map((entry) => entry.kind)).toEqual(['added', 'modified', 'removed']);
    expect(laid.map((entry) => entry.id).sort()).toEqual(plain.map((entry) => entry.id).sort());
  });

  it('양식이 가리키는 자리가 변경안 블록에 실재한다 — 없으면 순서 검사가 공허하다', () => {
    for (const item of PROPOSED_WIKI_LAYOUT) {
      if (item.kind === 'block') expect(PROPOSED_WIKI_BLOCKS[item.blockIndex]).toBeDefined();
    }
  });

  it('사유 문구는 서버 문체(존댓말) 표본이다 — 컴파일 문장과 개수 문구가 같은 자리에 섞인다', () => {
    const reasons = [...PROPOSED_WIKI_BLOCKS, ...LONG_PROPOSED_WIKI_BLOCKS]
      .map((wikiBlock) => wikiBlock.reason)
      .filter((reason): reason is string => Boolean(reason));

    expect(reasons.length).toBeGreaterThan(0);
    for (const reason of reasons) expect(reason).toMatch(/니다\.$/);
  });

  it('긴 문단 쌍은 modified 한 카드를 내고 단어 강조를 포함한다', () => {
    const entries = buildBlockDiff(LONG_BASE_WIKI_BLOCKS, LONG_PROPOSED_WIKI_BLOCKS, SINGLE_MODIFIED_BLOCK_CHANGES);
    expect(entries).toHaveLength(1);
    expect(entries[0].kind).toBe('modified');
    expect(entries[0].after!.some((line) => line.segments.some((s) => s.emphasized))).toBe(true);
  });

  it('판정 경로 키는 변경안 블록에서만 실린다 — removed 카드는 둘 다 없음이다', () => {
    const entries = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);
    const [modified, added, removed] = entries;

    expect(modified).toMatchObject({ blockIndex: 0 });
    expect(added).toMatchObject({ blockIndex: 1 });
    expect(modified.blockContentHash).toMatch(/^sha256:/);
    expect(added.blockContentHash).toMatch(/^sha256:/);
    expect(removed).toMatchObject({ blockIndex: null, blockContentHash: null, reason: null });
  });

  it('변경안 블록의 자리는 배열 자리와 같다 (서버 enumerate 계약)', () => {
    PROPOSED_WIKI_BLOCKS.forEach((wikiBlock, index) => expect(wikiBlock.blockIndex).toBe(index));
    BASE_WIKI_BLOCKS.forEach((wikiBlock, index) => expect(wikiBlock.blockIndex).toBe(index));
  });

  it('다툼 블록은 sources를 비우고 variants에만 근거를 싣는다', () => {
    const [contested] = CONTESTED_PROPOSED_BLOCKS;
    expect(contested.sources).toHaveLength(0);
    expect(contested.variants).not.toBeNull();
    expect(contested.variants).toHaveLength(2);
    for (const variant of contested.variants!) {
      expect(variant.sources.length).toBeGreaterThan(0);
    }
  });

  it('다툼 아닌 블록의 variants는 빈 배열이 아니라 null이다', () => {
    // 백엔드가 기본값 []를 거부한 이유 — "후보 없음"과 "다투는데 후보가 빔"을 구별해야 한다
    for (const wikiBlock of PROPOSED_WIKI_BLOCKS) {
      expect(wikiBlock.variants).toBeNull();
    }
  });

  it('저장된 반려 판정이 카드의 rejected로 이어진다', () => {
    const [entry] = buildBlockDiff(BASE_WIKI_BLOCKS, JUDGED_PROPOSED_BLOCKS, SINGLE_MODIFIED_BLOCK_CHANGES);
    expect(entry.rejected).toBe(true);
  });

  it('산문 있는 블록과 없는 블록이 모두 표본에 있다 (폴백 경로 표본)', () => {
    const all = [...BASE_WIKI_BLOCKS, ...PROPOSED_WIKI_BLOCKS];
    expect(all.some((wikiBlock) => wikiBlock.narrative !== null)).toBe(true);
    expect(all.some((wikiBlock) => wikiBlock.narrative === null)).toBe(true);
  });

  it('산문이 있으면 표시 본문은 산문이다 — body 값 표기는 화면에 실리지 않는다', () => {
    const [modified] = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);
    expect(flatten(modified.after)).toBe(PROPOSED_WIKI_BLOCKS[0].narrative);
    expect(flatten(modified.after)).not.toContain('3회까지');
  });

  it('산문이 없으면 body로 폴백한다 (옛 데이터)', () => {
    const entries = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);
    const added = entries.find((entry) => entry.kind === 'added')!;
    expect(flatten(added.after)).toBe(PROPOSED_WIKI_BLOCKS[1].body);
  });

  it('한쪽만 산문인 쌍은 양쪽 다 body로 비교한다 — 축이 섞이면 전부 바뀐 것처럼 보인다', () => {
    // BASE는 산문이 있고 JUDGED는 없다
    const [entry] = buildBlockDiff([BASE_WIKI_BLOCKS[0]], JUDGED_PROPOSED_BLOCKS, SINGLE_MODIFIED_BLOCK_CHANGES);
    expect(flatten(entry.before)).toBe(BASE_WIKI_BLOCKS[0].body);
    expect(flatten(entry.after)).toBe(JUDGED_PROPOSED_BLOCKS[0].body);
  });

  it('같은 본문이면 같은 지문이다 (낙관적 잠금 mock의 전제)', () => {
    const judged = JUDGED_PROPOSED_BLOCKS[0];
    const proposed = PROPOSED_WIKI_BLOCKS[0];
    expect(judged.body).toBe(proposed.body);
    expect(judged.blockContentHash).toBe(proposed.blockContentHash);
  });
});
