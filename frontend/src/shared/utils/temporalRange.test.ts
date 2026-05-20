import { describe, expect, it } from 'vitest';

import {
  dateRangeToUrlParams,
  sortByRelevance,
  sortByUpdatedAt,
  toApiTemporalParams,
  urlParamsToDateRange,
} from './temporalRange';

describe('dateRangeToUrlParams', () => {
  it('from·to를 yyyy-MM-dd 문자열로 변환한다', () => {
    const range = { from: new Date(2026, 4, 1), to: new Date(2026, 4, 19) };
    expect(dateRangeToUrlParams(range)).toEqual({ start: '2026-05-01', end: '2026-05-19' });
  });

  it('to가 없으면 end를 start와 동일하게 둔다', () => {
    expect(dateRangeToUrlParams({ from: new Date(2026, 4, 1) })).toEqual({
      start: '2026-05-01',
      end: '2026-05-01',
    });
  });

  it('range가 없거나 from이 없으면 빈 객체', () => {
    expect(dateRangeToUrlParams(undefined)).toEqual({});
    expect(dateRangeToUrlParams({ from: undefined })).toEqual({});
  });
});

describe('urlParamsToDateRange', () => {
  it('yyyy-MM-dd 문자열을 로컬 자정 Date의 DateRange로 복원한다', () => {
    const range = urlParamsToDateRange('2026-05-01', '2026-05-19');
    expect(range?.from).toEqual(new Date(2026, 4, 1));
    expect(range?.to).toEqual(new Date(2026, 4, 19));
  });

  it('end가 없으면 to를 from과 동일하게 둔다', () => {
    const range = urlParamsToDateRange('2026-05-01', null);
    expect(range?.to).toEqual(new Date(2026, 4, 1));
  });

  it('start가 없거나 형식이 잘못되면 undefined', () => {
    expect(urlParamsToDateRange(null, null)).toBeUndefined();
    expect(urlParamsToDateRange('2026/05/01', null)).toBeUndefined();
  });
});

describe('toApiTemporalParams', () => {
  it('KST 일자를 UTC datetime으로 변환한다 (start=KST 자정, end=다음날 KST 자정)', () => {
    expect(toApiTemporalParams('2026-05-01', '2026-05-19')).toEqual({
      start_date: '2026-04-30T15:00:00.000Z',
      end_date: '2026-05-19T15:00:00.000Z',
    });
  });

  it('한쪽만 있어도 그쪽만 변환한다', () => {
    expect(toApiTemporalParams('2026-05-01', undefined)).toEqual({
      start_date: '2026-04-30T15:00:00.000Z',
    });
  });

  it('형식이 잘못된 값은 무시한다', () => {
    expect(toApiTemporalParams('bad', 'bad')).toEqual({});
  });
});

describe('sortByUpdatedAt', () => {
  const items = [
    { id: 'a', updated_at: '2026-05-10T00:00:00Z' },
    { id: 'b', updated_at: '2026-05-20T00:00:00Z' },
    { id: 'c', updated_at: '2026-05-01T00:00:00Z' },
  ];

  it('newest는 updated_at 내림차순', () => {
    expect(sortByUpdatedAt(items, 'newest').map((x) => x.id)).toEqual(['b', 'a', 'c']);
  });

  it('oldest는 updated_at 오름차순', () => {
    expect(sortByUpdatedAt(items, 'oldest').map((x) => x.id)).toEqual(['c', 'a', 'b']);
  });

  it('updated_at 없는 항목은 끝으로, 원본 순서 유지', () => {
    const withNull = [
      { id: 'x', updated_at: null },
      { id: 'y', updated_at: '2026-05-01T00:00:00Z' },
    ];
    expect(sortByUpdatedAt(withNull, 'newest').map((x) => x.id)).toEqual(['y', 'x']);
  });

  it('원본 배열을 변경하지 않는다', () => {
    const copy = [...items];
    sortByUpdatedAt(items, 'newest');
    expect(items).toEqual(copy);
  });

  it('같은 KST 일자 그룹 안에서 relevance_score desc로 tiebreak (newest)', () => {
    // 두 항목 모두 KST 5/10 (01:00Z=10:00 KST, 14:00Z=23:00 KST), other는 5/11.
    const sameDay = [
      { id: 'lo', updated_at: '2026-05-10T01:00:00Z', relevance_score: 0.3 },
      { id: 'hi', updated_at: '2026-05-10T14:00:00Z', relevance_score: 0.9 },
      { id: 'other', updated_at: '2026-05-11T01:00:00Z', relevance_score: 0.5 },
    ];
    expect(sortByUpdatedAt(sameDay, 'newest').map((x) => x.id)).toEqual(['other', 'hi', 'lo']);
  });

  it('같은 KST 일자 그룹 안에서 relevance_score desc로 tiebreak (oldest)', () => {
    const sameDay = [
      { id: 'lo', updated_at: '2026-05-10T01:00:00Z', relevance_score: 0.3 },
      { id: 'hi', updated_at: '2026-05-10T14:00:00Z', relevance_score: 0.9 },
      { id: 'other', updated_at: '2026-05-11T01:00:00Z', relevance_score: 0.5 },
    ];
    expect(sortByUpdatedAt(sameDay, 'oldest').map((x) => x.id)).toEqual(['hi', 'lo', 'other']);
  });

  it('다른 KST 일자면 일자 순서가 우선 — relevance 무시', () => {
    const diffDays = [
      { id: 'old-hi', updated_at: '2026-05-01T00:00:00Z', relevance_score: 0.95 },
      { id: 'new-lo', updated_at: '2026-05-20T00:00:00Z', relevance_score: 0.05 },
    ];
    expect(sortByUpdatedAt(diffDays, 'newest').map((x) => x.id)).toEqual(['new-lo', 'old-hi']);
  });
});

describe('sortByRelevance', () => {
  it('relevance_score desc로 정렬', () => {
    const byScore = [
      { id: 'mid', relevance_score: 0.5, updated_at: '2026-05-10T00:00:00Z' },
      { id: 'hi', relevance_score: 0.9, updated_at: '2026-05-01T00:00:00Z' },
      { id: 'lo', relevance_score: 0.1, updated_at: '2026-05-20T00:00:00Z' },
    ];
    expect(sortByRelevance(byScore).map((x) => x.id)).toEqual(['hi', 'mid', 'lo']);
  });

  it('score 동률 시 updated_at desc로 tiebreak', () => {
    const tieScore = [
      { id: 'old', relevance_score: 0.5, updated_at: '2026-05-01T00:00:00Z' },
      { id: 'new', relevance_score: 0.5, updated_at: '2026-05-10T00:00:00Z' },
    ];
    expect(sortByRelevance(tieScore).map((x) => x.id)).toEqual(['new', 'old']);
  });

  it('relevance_score 누락 항목은 끝으로', () => {
    const missing = [
      { id: 'has', relevance_score: 0.5, updated_at: '2026-05-01T00:00:00Z' },
      { id: 'none', updated_at: '2026-05-10T00:00:00Z' },
    ];
    expect(sortByRelevance(missing).map((x) => x.id)).toEqual(['has', 'none']);
  });

  it('원본 배열을 변경하지 않는다', () => {
    const items = [
      { id: 'a', relevance_score: 0.1 },
      { id: 'b', relevance_score: 0.9 },
    ];
    const copy = [...items];
    sortByRelevance(items);
    expect(items).toEqual(copy);
  });
});
