import { describe, expect, it } from 'vitest';

import type { BlockChange, WikiBlock } from '../../types/llmWikiDiff';
import { buildBlockDiff } from './buildBlockDiff';

const block = (overrides: Partial<WikiBlock>): WikiBlock => ({
  blockIndex: 0,
  kind: 'claim_section',
  heading: '재시도 정책',
  body: '결제 승인 실패 시 1회 재시도한다.',
  narrative: null,
  claimIds: ['c-retry-1'],
  proposalIds: ['prop-1'],
  ontologyVersion: 'v1',
  blockContentHash: 'sha256:test',
  sources: [],
  variants: null,
  verdict: null,
  ...overrides,
});

const change = (overrides: Partial<BlockChange>): BlockChange => ({
  kind: 'modified',
  blockIndex: 0,
  baseBlockIndex: 0,
  ...overrides,
});

describe('buildBlockDiff', () => {
  it('modified는 좌우 본문을 모두 싣고 서버 사유를 옮긴다', () => {
    const entries = buildBlockDiff(
      [block({})],
      [block({ body: '결제 승인 실패 시 3회까지 재시도한다.', reason: '근거 1건 추가·0건 폐기' })],
      [change({})],
    );

    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({ kind: 'modified', title: '재시도 정책', reason: '근거 1건 추가·0건 폐기' });
    expect(entries[0].before).not.toBeNull();
    expect(entries[0].after).not.toBeNull();
  });

  it('변경 목록에 없는 블록은 카드가 되지 않는다 (미변경 블록)', () => {
    const entries = buildBlockDiff([block({}), block({ blockIndex: 1 })], [block({}), block({ blockIndex: 1 })], []);
    expect(entries).toHaveLength(0);
  });

  it('added는 after만, removed는 before만 채운다', () => {
    const entries = buildBlockDiff(
      [block({ heading: '수동 재시도 안내', body: '상담원이 안내한다.' })],
      [block({ heading: 'PG 점검 예외', body: '점검 시간에는 중단한다.', reason: '새 섹션' })],
      [change({ kind: 'added', blockIndex: 0, baseBlockIndex: null }), change({ kind: 'removed', blockIndex: null })],
    );

    expect(entries.map((entry) => entry.kind)).toEqual(['added', 'removed']);
    const [added, removed] = entries;
    expect(added.before).toBeNull();
    expect(added.after).not.toBeNull();
    expect(removed.before![0].segments[0].text).toBe('상담원이 안내한다.');
    expect(removed.after).toBeNull();
  });

  it('removed 카드에는 판정 경로와 사유가 없다 — 변경안에 자리가 없기 때문이다', () => {
    const entries = buildBlockDiff(
      [block({ heading: '사라진 블록', body: '내용' })],
      [],
      [change({ kind: 'removed', blockIndex: null })],
    );

    expect(entries[0]).toMatchObject({ blockIndex: null, blockContentHash: null, reason: null });
  });

  it('자리가 범위를 벗어난 변경은 건너뛴다', () => {
    const entries = buildBlockDiff([], [], [change({}), change({ kind: 'added', baseBlockIndex: null })]);
    expect(entries).toHaveLength(0);
  });

  it('판정 경로 키는 변경안 블록이 들고 있는 값을 그대로 쓴다', () => {
    const entries = buildBlockDiff(
      [block({}), block({ blockIndex: 1, heading: '다른 블록', body: 'x' })],
      [block({}), block({ blockIndex: 1, heading: '다른 블록', body: 'y', blockContentHash: 'sha256:second' })],
      [change({ kind: 'modified', blockIndex: 1, baseBlockIndex: 1 })],
    );

    expect(entries[0]).toMatchObject({ blockIndex: 1, blockContentHash: 'sha256:second' });
  });

  it('저장된 반려 판정이 카드의 rejected로 이어진다', () => {
    const entries = buildBlockDiff(
      [block({})],
      [
        block({
          body: '바뀐 본문',
          verdict: {
            proposalId: 'prop-1',
            blockIndex: 0,
            blockContentHash: 'sha256:test',
            verdict: 'rejected',
            rejectionReason: '근거 부족',
            chosenWinnerClaimId: null,
            reviewer: '직원10',
            reviewedAt: '2026-08-10T01:20:00Z',
          },
        }),
      ],
      [change({})],
    );

    expect(entries[0].rejected).toBe(true);
  });

  it('modified의 삭제분은 before에서만, 추가분은 after에서만 emphasized', () => {
    const [entry] = buildBlockDiff(
      [block({ body: '실패 시 1회 재시도한다.' })],
      [block({ body: '실패 시 3회까지 재시도한다.' })],
      [change({})],
    );

    const beforeTexts = entry.before!.flatMap((line) => line.segments.filter((s) => s.emphasized)).map((s) => s.text);
    const afterTexts = entry.after!.flatMap((line) => line.segments.filter((s) => s.emphasized)).map((s) => s.text);

    expect(beforeTexts.join('')).toContain('1회');
    expect(beforeTexts.join('')).not.toContain('3회');
    expect(afterTexts.join('')).toContain('3회까지');
    expect(afterTexts.join('')).not.toContain('1회');
  });

  it('줄바꿈이 DiffLine 경계가 된다', () => {
    const [entry] = buildBlockDiff(
      [block({ body: '첫 줄이다.\n둘째 줄이다.' })],
      [block({ body: '첫 줄이 바뀌었다.\n둘째 줄이다.' })],
      [change({})],
    );

    expect(entry.before).toHaveLength(2);
    expect(entry.after).toHaveLength(2);
    expect(entry.after![1].segments.every((s) => !s.emphasized)).toBe(true);
  });

  it('레이아웃이 있으면 카드 순서가 그 양식을 따른다', () => {
    const entries = buildBlockDiff(
      [block({}), block({ blockIndex: 1, heading: '두 번째', body: 'b' })],
      [block({ body: 'a2' }), block({ blockIndex: 1, heading: '두 번째', body: 'b2' })],
      [change({ blockIndex: 0, baseBlockIndex: 0 }), change({ blockIndex: 1, baseBlockIndex: 1 })],
      [
        { kind: 'block', heading: '두 번째', blockIndex: 1 },
        { kind: 'block', heading: '재시도 정책', blockIndex: 0 },
      ],
    );

    expect(entries.map((entry) => entry.blockIndex)).toEqual([1, 0]);
  });

  it('표로 묶인 블록들은 그 표 자리에 함께 선다', () => {
    const entries = buildBlockDiff(
      [block({}), block({ blockIndex: 1, body: 'b' }), block({ blockIndex: 2, body: 'c' })],
      [block({ body: 'a2' }), block({ blockIndex: 1, body: 'b2' }), block({ blockIndex: 2, body: 'c2' })],
      [
        change({ blockIndex: 0 }),
        change({ blockIndex: 1, baseBlockIndex: 1 }),
        change({ blockIndex: 2, baseBlockIndex: 2 }),
      ],
      [
        { kind: 'table', heading: '사용 상황', blockIndexes: [1, 2], rows: [] },
        { kind: 'block', heading: '요청 상태', blockIndex: 0 },
      ],
    );

    expect(entries.map((entry) => entry.blockIndex)).toEqual([1, 2, 0]);
  });

  it('양식이 이름을 대지 않은 카드는 원래 순서대로 뒤에 남는다 — 빠진 블록이 그렇다', () => {
    const entries = buildBlockDiff(
      [block({ heading: '사라진 블록', body: 'gone' }), block({ blockIndex: 1, body: 'b' })],
      [block({ body: 'a2' })],
      [change({ kind: 'removed', blockIndex: null, baseBlockIndex: 0 }), change({ blockIndex: 0, baseBlockIndex: 1 })],
      [{ kind: 'block', heading: '재시도 정책', blockIndex: 0 }],
    );

    expect(entries.map((entry) => entry.kind)).toEqual(['modified', 'removed']);
  });

  it('레이아웃이 순서만 바꾼다 — 판정 키는 카드마다 그대로다', () => {
    const entries = buildBlockDiff(
      [block({}), block({ blockIndex: 1, body: 'b' })],
      [block({ body: 'a2' }), block({ blockIndex: 1, body: 'b2', blockContentHash: 'sha256:second' })],
      [change({ blockIndex: 0 }), change({ blockIndex: 1, baseBlockIndex: 1 })],
      [
        { kind: 'block', heading: '두 번째', blockIndex: 1 },
        { kind: 'block', heading: '재시도 정책', blockIndex: 0 },
      ],
    );

    expect(entries[0]).toMatchObject({ blockIndex: 1, blockContentHash: 'sha256:second', id: 'modified-1' });
    expect(entries[1]).toMatchObject({ blockIndex: 0, blockContentHash: 'sha256:test', id: 'modified-0' });
  });

  it('레이아웃이 비면 서버 변경 목록 순서 그대로다 — 구서버 응답 경로다', () => {
    const entries = buildBlockDiff(
      [block({}), block({ blockIndex: 1, body: 'b' })],
      [block({ body: 'a2' }), block({ blockIndex: 1, body: 'b2' })],
      [change({ blockIndex: 1, baseBlockIndex: 1 }), change({ blockIndex: 0, baseBlockIndex: 0 })],
    );

    expect(entries.map((entry) => entry.blockIndex)).toEqual([1, 0]);
  });

  it('added·removed 카드에는 단어 강조가 없다 (패널 색이 전부)', () => {
    const entries = buildBlockDiff(
      [block({ body: '지워질 내용' })],
      [block({ body: '새 내용' })],
      [change({ kind: 'added', baseBlockIndex: null }), change({ kind: 'removed', blockIndex: null })],
    );

    for (const entry of entries) {
      for (const line of entry.before ?? entry.after ?? []) {
        expect(line.segments.every((s) => !s.emphasized)).toBe(true);
      }
    }
  });
});
