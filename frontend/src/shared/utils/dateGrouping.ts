import type { FilterOption } from '@/shared/components/ui/filter-dropdown';

/* ── 타입 ─────────────────────────────────────── */

/** 날짜 그룹 키 (오늘 / 최근 7일 / 이전) */
export type DateGroup = 'today' | 'sevenDays' | 'older';

/** 기간 필터 값 ('all' 포함) */
export type DatePeriod = 'all' | DateGroup;

/** 정렬 기준 */
export type SortOrder = 'latest' | 'oldest';

/** 날짜 그룹별로 묶인 섹션 */
export interface GroupedSection<T> {
  key: DateGroup;
  title: string;
  items: T[];
}

/* ── 상수 ─────────────────────────────────────── */

/** 정렬 드롭다운 옵션 */
export const SORT_OPTIONS: readonly FilterOption<SortOrder>[] = [
  { value: 'latest', label: '최신순' },
  { value: 'oldest', label: '오래된순' },
] as const;

/** 기간 필터 드롭다운 옵션 */
export const PERIOD_OPTIONS: readonly FilterOption<DatePeriod>[] = [
  { value: 'all', label: '전체' },
  { value: 'today', label: '오늘' },
  { value: 'sevenDays', label: '최근 7일' },
  { value: 'older', label: '이전' },
] as const;

/** 날짜 그룹별 섹션 제목 */
export const DATE_SECTION_LABELS: Record<DateGroup, string> = {
  today: '오늘',
  sevenDays: '최근 7일',
  older: '이전',
};

/** 섹션 렌더링 순서 */
export const DATE_GROUP_ORDER: readonly DateGroup[] = ['today', 'sevenDays', 'older'] as const;

/* ── 유틸 함수 ────────────────────────────────── */

const normalizeDate = (date: Date): Date => {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
};

/** 날짜를 기준으로 그룹(오늘 / 최근 7일 / 이전) 결정 */
export const getDateGroup = (rawDate: Date): DateGroup => {
  const itemDate = normalizeDate(rawDate);
  const today = normalizeDate(new Date());

  if (itemDate.getTime() === today.getTime()) return 'today';

  const sevenDaysAgo = normalizeDate(new Date());
  sevenDaysAgo.setDate(today.getDate() - 7);

  if (itemDate.getTime() >= sevenDaysAgo.getTime()) return 'sevenDays';

  return 'older';
};

/** 아이템이 지정된 기간 필터에 해당하는지 판별 */
export const isInPeriod = (rawDate: Date, period: DatePeriod): boolean => {
  if (period === 'all') return true;
  const group = getDateGroup(rawDate);
  if (period === 'sevenDays') return group === 'today' || group === 'sevenDays';
  return group === period;
};

/** 아이템 목록을 날짜 그룹별 섹션으로 변환 */
export const groupItemsByDate = <T>(items: T[], getDate: (item: T) => Date): GroupedSection<T>[] => {
  const grouped: Record<DateGroup, T[]> = { today: [], sevenDays: [], older: [] };

  for (const item of items) {
    const group = getDateGroup(getDate(item));
    grouped[group].push(item);
  }

  return DATE_GROUP_ORDER.filter((group) => grouped[group].length > 0).map((group) => ({
    key: group,
    title: DATE_SECTION_LABELS[group],
    items: grouped[group],
  }));
};
