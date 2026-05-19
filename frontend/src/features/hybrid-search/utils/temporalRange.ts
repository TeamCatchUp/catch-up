// 문서 탐색 기간 필터 날짜 변환 + 결과 정렬 유틸.
// URL은 KST 일자(yyyy-MM-dd), 백엔드 API는 UTC datetime을 쓴다.

import { format } from 'date-fns';
import type { DateRange } from 'react-day-picker';

const DATE_FMT = 'yyyy-MM-dd';
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export type SortOrder = 'newest' | 'oldest';

// yyyy-MM-dd 문자열을 로컬 자정 Date로 파싱. 형식 오류 시 undefined.
function parseLocalDate(value: string | null | undefined): Date | undefined {
  if (!value || !DATE_RE.test(value)) return undefined;
  const [y, m, d] = value.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

// DateRange(Date 객체) → URL 쿼리용 yyyy-MM-dd 문자열. to 없으면 end=start.
export function dateRangeToUrlParams(range: DateRange | undefined): { start?: string; end?: string } {
  if (!range?.from) return {};
  const start = format(range.from, DATE_FMT);
  return { start, end: range.to ? format(range.to, DATE_FMT) : start };
}

// URL 쿼리(yyyy-MM-dd) → DateRange. start가 없거나 잘못되면 undefined.
export function urlParamsToDateRange(
  start: string | null,
  end: string | null,
): DateRange | undefined {
  const from = parseLocalDate(start);
  if (!from) return undefined;
  return { from, to: parseLocalDate(end) ?? from };
}

// KST 일자(yyyy-MM-dd) → 백엔드 API용 UTC ISO datetime.
export function toApiTemporalParams(
  start: string | undefined,
  end: string | undefined,
): { start_date?: string; end_date?: string } {
  const params: { start_date?: string; end_date?: string } = {};
  if (start && DATE_RE.test(start)) {
    params.start_date = new Date(`${start}T00:00:00.000+09:00`).toISOString();
  }
  if (end && DATE_RE.test(end)) {
    params.end_date = new Date(`${end}T23:59:59.999+09:00`).toISOString();
  }
  return params;
}

// created_at 기준 정렬. created_at 없는 항목은 끝으로. 원본 불변.
export function sortByCreatedAt<T extends { created_at?: string | null }>(
  items: readonly T[],
  order: SortOrder,
): T[] {
  return [...items].sort((a, b) => {
    const ta = a.created_at ? Date.parse(a.created_at) : NaN;
    const tb = b.created_at ? Date.parse(b.created_at) : NaN;
    const aNaN = Number.isNaN(ta);
    const bNaN = Number.isNaN(tb);
    if (aNaN && bNaN) return 0;
    if (aNaN) return 1;
    if (bNaN) return -1;
    return order === 'newest' ? tb - ta : ta - tb;
  });
}
