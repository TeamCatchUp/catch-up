// 문서 탐색 기간 필터 날짜 변환 + 결과 정렬 유틸.
// URL은 KST 일자(yyyy-MM-dd), 백엔드 API는 UTC datetime을 쓴다.

import type { DateRange } from 'react-day-picker';
import { format } from 'date-fns';

const DATE_FMT = 'yyyy-MM-dd';
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export type SortOrder = 'relevance' | 'newest' | 'oldest';

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
    // end 다음날 KST 자정을 상한으로 — 백엔드 inclusive/exclusive 비교 모두 정합.
    const endBound = new Date(`${end}T00:00:00.000+09:00`);
    endBound.setUTCDate(endBound.getUTCDate() + 1);
    params.end_date = endBound.toISOString();
  }
  return params;
}

// KST 자정 기준 day index — "표시 라벨 동일" 판정의 정수 키.
// UTC ms를 9h 시프트 후 1일(86_400_000ms)로 floor.
function kstDayIndex(iso: string): number | null {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  return Math.floor((t + 9 * 3_600_000) / 86_400_000);
}

// relevance_score desc 비교. 누락은 끝으로.
function compareRelevanceDesc<T extends { relevance_score?: number }>(a: T, b: T): number {
  const sa = a.relevance_score;
  const sb = b.relevance_score;
  if (sa === undefined && sb === undefined) return 0;
  if (sa === undefined) return 1;
  if (sb === undefined) return -1;
  return sb - sa;
}

// updated_at 기준 정렬. 같은 KST 일자 내에서는 relevance_score desc로 tiebreak.
// updated_at 없는 항목은 끝으로. 원본 불변.
export function sortByUpdatedAt<T extends { updated_at?: string | null; relevance_score?: number }>(
  items: readonly T[],
  order: 'newest' | 'oldest',
): T[] {
  return [...items].sort((a, b) => {
    const da = a.updated_at ? kstDayIndex(a.updated_at) : null;
    const db = b.updated_at ? kstDayIndex(b.updated_at) : null;
    if (da === null && db === null) return 0;
    if (da === null) return 1;
    if (db === null) return -1;
    if (da !== db) return order === 'newest' ? db - da : da - db;
    return compareRelevanceDesc(a, b);
  });
}

// relevance_score desc 정렬. score 동률 시 updated_at desc로 tiebreak.
// score 누락 항목은 끝으로. 원본 불변.
export function sortByRelevance<T extends { relevance_score?: number; updated_at?: string | null }>(
  items: readonly T[],
): T[] {
  return [...items].sort((a, b) => {
    const r = compareRelevanceDesc(a, b);
    if (r !== 0) return r;
    const ta = a.updated_at ? Date.parse(a.updated_at) : NaN;
    const tb = b.updated_at ? Date.parse(b.updated_at) : NaN;
    if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
    if (Number.isNaN(ta)) return 1;
    if (Number.isNaN(tb)) return -1;
    return tb - ta;
  });
}
