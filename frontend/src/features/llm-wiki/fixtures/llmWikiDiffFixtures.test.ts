import { describe, expect, it } from 'vitest';

import { computeBlockDiff } from '../utils/diff/computeBlockDiff';
import {
  BASE_WIKI_BLOCKS,
  CONTESTED_PROPOSED_BLOCKS,
  JUDGED_PROPOSED_BLOCKS,
  LONG_BASE_WIKI_BLOCKS,
  LONG_PROPOSED_WIKI_BLOCKS,
  PROPOSED_WIKI_BLOCKS,
} from './llmWikiDiffFixtures';

describe('llmWikiDiffFixtures', () => {
  it('기본 쌍은 modified → added → removed 세 카드를 낸다 (스토리 계약)', () => {
    const entries = computeBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS);
    expect(entries.map((e) => e.kind)).toEqual(['modified', 'added', 'removed']);
    expect(entries.map((e) => e.title)).toEqual(['재시도 정책', 'PG 점검 시간 예외', '수동 재시도 안내']);
  });

  it('긴 문단 쌍은 modified 한 카드를 내고 단어 강조를 포함한다', () => {
    const entries = computeBlockDiff(LONG_BASE_WIKI_BLOCKS, LONG_PROPOSED_WIKI_BLOCKS);
    expect(entries).toHaveLength(1);
    expect(entries[0].kind).toBe('modified');
    expect(entries[0].after!.some((line) => line.segments.some((s) => s.emphasized))).toBe(true);
  });

  it('판정 경로 키(blockIndex·blockContentHash)가 proposed 블록에서 실린다', () => {
    const entries = computeBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS);
    for (const [index, entry] of entries.entries()) {
      expect(entry.blockIndex).toBe(index);
      expect(entry.blockContentHash).toMatch(/^sha256:/);
    }
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
    const [entry] = computeBlockDiff(BASE_WIKI_BLOCKS, JUDGED_PROPOSED_BLOCKS);
    expect(entry.rejected).toBe(true);
  });

  it('같은 본문이면 같은 지문이다 (낙관적 잠금 mock의 전제)', () => {
    const judged = JUDGED_PROPOSED_BLOCKS[0];
    const proposed = PROPOSED_WIKI_BLOCKS[0];
    expect(judged.body).toBe(proposed.body);
    expect(judged.blockContentHash).toBe(proposed.blockContentHash);
  });
});
