import { describe, expect, it } from 'vitest';

import type { WikiBlock } from '../../types/llmWikiDiff';
import { computeBlockDiff } from './computeBlockDiff';

const block = (overrides: Partial<WikiBlock>): WikiBlock => ({
  kind: 'claim_section',
  heading: '재시도 정책',
  body: '결제 승인 실패 시 1회 재시도한다.',
  claimIds: ['c-retry-1'],
  ...overrides,
});

describe('computeBlockDiff', () => {
  it('claimIds 교집합 쌍의 body가 다르면 modified 카드가 된다', () => {
    const entries = computeBlockDiff(
      [block({})],
      [block({ body: '결제 승인 실패 시 3회까지 재시도한다.', reason: 'VOC 3건' })],
    );

    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({ kind: 'modified', title: '재시도 정책', reason: 'VOC 3건' });
    expect(entries[0].before).not.toBeNull();
    expect(entries[0].after).not.toBeNull();
  });

  it('body가 같으면 카드를 만들지 않는다 (heading 변경 감지는 MVP 밖)', () => {
    const entries = computeBlockDiff([block({})], [block({ heading: '다른 제목' })]);
    expect(entries).toHaveLength(0);
  });

  it('proposed에만 있으면 added, base에만 있으면 removed', () => {
    const entries = computeBlockDiff(
      [block({ heading: '수동 재시도 안내', body: '상담원이 안내한다.', claimIds: ['c-manual-1'] })],
      [block({ heading: 'PG 점검 예외', body: '점검 시간에는 중단한다.', claimIds: ['c-pg-1'] })],
    );

    expect(entries.map((e) => e.kind)).toEqual(['added', 'removed']);
    const [added, removed] = entries;
    expect(added.before).toBeNull();
    expect(added.after).not.toBeNull();
    expect(removed.before).not.toBeNull();
    expect(removed.after).toBeNull();
  });

  it('삭제 tombstone은 원문을 base에서 가져오고 사유를 싣는다', () => {
    const entries = computeBlockDiff(
      [block({ heading: '수동 재시도 안내', body: '상담원이 안내한다.', claimIds: ['c-manual-1'] })],
      [block({ heading: '수동 재시도 안내', body: '', claimIds: ['c-manual-1'], removed: true, reason: '절차 폐지' })],
    );

    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({ kind: 'removed', title: '수동 재시도 안내', reason: '절차 폐지' });
    expect(entries[0].after).toBeNull();
    // tombstone의 빈 body가 아니라 base의 원문이 보여야 한다
    expect(entries[0].before![0].segments[0].text).toBe('상담원이 안내한다.');
  });

  it('tombstone 없이 빠진 블록도 카드가 되지만 사유가 없다 (계약 위반 신호)', () => {
    const entries = computeBlockDiff(
      [block({ heading: '사라진 블록', body: '내용', claimIds: ['c-gone'] })],
      [],
    );

    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({ kind: 'removed', reason: null });
  });

  it('claimIds가 비면 페어링되지 않고 added+removed로 갈라진다', () => {
    const entries = computeBlockDiff(
      [block({ claimIds: [] })],
      [block({ claimIds: [], body: '내용이 다르다.' })],
    );
    expect(entries.map((e) => e.kind)).toEqual(['added', 'removed']);
  });

  it('modified의 삭제분은 before에서만, 추가분은 after에서만 emphasized', () => {
    const [entry] = computeBlockDiff(
      [block({ body: '실패 시 1회 재시도한다.' })],
      [block({ body: '실패 시 3회까지 재시도한다.' })],
    );

    const beforeTexts = entry
      .before!.flatMap((line) => line.segments.filter((s) => s.emphasized))
      .map((s) => s.text);
    const afterTexts = entry
      .after!.flatMap((line) => line.segments.filter((s) => s.emphasized))
      .map((s) => s.text);

    expect(beforeTexts.join('')).toContain('1회');
    expect(beforeTexts.join('')).not.toContain('3회');
    expect(afterTexts.join('')).toContain('3회까지');
    expect(afterTexts.join('')).not.toContain('1회');
  });

  it('줄바꿈이 DiffLine 경계가 된다', () => {
    const [entry] = computeBlockDiff(
      [block({ body: '첫 줄이다.\n둘째 줄이다.' })],
      [block({ body: '첫 줄이 바뀌었다.\n둘째 줄이다.' })],
    );

    expect(entry.before).toHaveLength(2);
    expect(entry.after).toHaveLength(2);
    // 바뀌지 않은 둘째 줄에는 강조가 없다
    expect(entry.after![1].segments.every((s) => !s.emphasized)).toBe(true);
  });

  it('added·removed 카드에는 단어 강조가 없다 (패널 색이 전부)', () => {
    const entries = computeBlockDiff(
      [block({ claimIds: ['c-a'], body: '지워질 내용' })],
      [block({ claimIds: ['c-b'], body: '새 내용' })],
    );
    for (const entry of entries) {
      for (const line of entry.before ?? entry.after ?? []) {
        expect(line.segments.every((s) => !s.emphasized)).toBe(true);
      }
    }
  });
});
