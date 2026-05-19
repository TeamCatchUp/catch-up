import { describe, expect, it } from 'vitest';

import {
  dateRangeToUrlParams,
  sortByCreatedAt,
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
  it('KST 일자를 UTC datetime으로 변환한다 (start=00:00, end=23:59:59.999)', () => {
    expect(toApiTemporalParams('2026-05-01', '2026-05-19')).toEqual({
      start_date: '2026-04-30T15:00:00.000Z',
      end_date: '2026-05-19T14:59:59.999Z',
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

describe('sortByCreatedAt', () => {
  const items = [
    { id: 'a', created_at: '2026-05-10T00:00:00Z' },
    { id: 'b', created_at: '2026-05-20T00:00:00Z' },
    { id: 'c', created_at: '2026-05-01T00:00:00Z' },
  ];

  it('newest는 created_at 내림차순', () => {
    expect(sortByCreatedAt(items, 'newest').map((x) => x.id)).toEqual(['b', 'a', 'c']);
  });

  it('oldest는 created_at 오름차순', () => {
    expect(sortByCreatedAt(items, 'oldest').map((x) => x.id)).toEqual(['c', 'a', 'b']);
  });

  it('created_at 없는 항목은 끝으로, 원본 순서 유지', () => {
    const withNull = [
      { id: 'x', created_at: null },
      { id: 'y', created_at: '2026-05-01T00:00:00Z' },
    ];
    expect(sortByCreatedAt(withNull, 'newest').map((x) => x.id)).toEqual(['y', 'x']);
  });

  it('원본 배열을 변경하지 않는다', () => {
    const copy = [...items];
    sortByCreatedAt(items, 'newest');
    expect(items).toEqual(copy);
  });
});
