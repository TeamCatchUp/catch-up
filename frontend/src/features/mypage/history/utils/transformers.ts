import type { RecentQueriesResponse } from '@/shared/types/query/api';
import { formatFullDate, formatRelativeDate } from '@/shared/utils/formatDate';

import type { HistoryGroup, HistoryItem, HistoryPeriod } from '../types/models';

type RecentQueryItem = RecentQueriesResponse['items'][number];

type RecentQueryItemWithSaved = RecentQueryItem & {
  is_saved?: boolean;
  is_bookmarked?: boolean;
  bookmarked?: boolean;
};

/**
 * 날짜의 시분초를 00:00:00으로 초기화하여 일(day) 단위 비교를 가능하게 한다.
 * @param date - 정규화할 Date 객체
 * @returns 시분초가 0으로 설정된 새 Date 객체
 */
const normalizeDate = (date: Date): Date => {
  const normalized = new Date(date);
  normalized.setHours(0, 0, 0, 0);
  return normalized;
};

/**
 * 날짜를 기준으로 히스토리 그룹(오늘 / 최근 7일 / 이전)을 결정한다.
 * @param rawDate - 판별 대상 Date 객체
 * @returns 해당 날짜가 속하는 {@link HistoryGroup} 키
 */
export const getHistoryGroup = (rawDate: Date): HistoryGroup => {
  const itemDate = normalizeDate(rawDate);
  const today = normalizeDate(new Date());

  if (itemDate.getTime() === today.getTime()) {
    return 'today';
  }

  const sevenDaysAgo = normalizeDate(new Date());
  sevenDaysAgo.setDate(today.getDate() - 7);

  if (itemDate.getTime() >= sevenDaysAgo.getTime()) {
    return 'sevenDays';
  }

  return 'older';
};

/**
 * API 응답의 최근 질문 아이템을 화면용 {@link HistoryItem}으로 변환한다.
 * @param item - API에서 받은 원시 질문 아이템
 * @returns 포맷된 날짜·저장 여부가 포함된 히스토리 아이템
 */
export const toHistoryItem = (item: RecentQueryItem): HistoryItem => {
  const rawDate = new Date(item.created_at);
  const withSaved = item as RecentQueryItemWithSaved;
  const isSaved = withSaved.is_saved ?? withSaved.is_bookmarked ?? withSaved.bookmarked ?? false;

  return {
    id: `${item.id}-${item.session_id}-${item.created_at}`,
    sessionId: item.session_id,
    query: item.content,
    createdAt: item.created_at,
    rawDate,
    fullDate: formatFullDate(item.created_at),
    relativeDate: formatRelativeDate(item.created_at),
    isSaved,
  };
};

/**
 * 히스토리 아이템이 지정된 기간 필터에 해당하는지 판별한다.
 * @param item - 검사 대상 히스토리 아이템
 * @param period - 적용할 기간 필터 (`'all'`이면 항상 `true`)
 * @returns 필터 조건 충족 여부
 */
export const isInPeriod = (item: HistoryItem, period: HistoryPeriod): boolean => {
  if (period === 'all') {
    return true;
  }
  return getHistoryGroup(item.rawDate) === period;
};
