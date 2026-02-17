import type { HistoryFilterOption, HistoryGroup, HistoryPeriod, HistorySort } from '../types/models';

/** 정렬 드롭다운 옵션 목록 */
export const HISTORY_SORT_OPTIONS: readonly HistoryFilterOption<HistorySort>[] = [
  { value: 'latest', label: '최신순' },
  { value: 'oldest', label: '오래된순' },
] as const;

/** 기간 필터 드롭다운 옵션 목록 */
export const HISTORY_PERIOD_OPTIONS: readonly HistoryFilterOption<HistoryPeriod>[] = [
  { value: 'all', label: '기간' },
  { value: 'today', label: '오늘' },
  { value: 'sevenDays', label: '최근 7일' },
  { value: 'older', label: '이전' },
] as const;

/** 날짜 그룹별 섹션 제목 매핑 */
export const HISTORY_SECTION_LABELS: Record<HistoryGroup, string> = {
  today: '오늘',
  sevenDays: '최근 7일',
  older: '이전',
};

/** 섹션 렌더링 순서를 결정하는 그룹 키 배열 */
export const HISTORY_GROUP_ORDER: readonly HistoryGroup[] = ['today', 'sevenDays', 'older'] as const;
