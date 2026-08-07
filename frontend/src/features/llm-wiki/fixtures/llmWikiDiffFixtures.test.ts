import { describe, expect, it } from 'vitest';

import { computeBlockDiff } from '../utils/diff/computeBlockDiff';
import {
  BASE_WIKI_BLOCKS,
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
});
