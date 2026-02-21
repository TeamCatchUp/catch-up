import type { RecentQueriesResponse } from '@/shared/types/query/api';
import { getDateGroup, isInPeriod as isInPeriodShared } from '@/shared/utils/dateGrouping';
import type { DatePeriod } from '@/shared/utils/dateGrouping';
import { formatFullDate, formatRelativeDate } from '@/shared/utils/formatDate';

import type { HistoryItem } from '../types/models';

type RecentQueryItem = RecentQueriesResponse['items'][number];

type RecentQueryItemWithSaved = RecentQueryItem & {
  is_saved?: boolean;
  is_bookmarked?: boolean;
  bookmarked?: boolean;
};

/** shared getDateGroup 래퍼 (기존 호출부 호환) */
export const getHistoryGroup = getDateGroup;

/**
 * API 응답의 최근 질문 아이템을 화면용 {@link HistoryItem}으로 변환한다.
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

/** 히스토리 아이템이 지정된 기간 필터에 해당하는지 판별 */
export const isInPeriod = (item: HistoryItem, period: DatePeriod): boolean => {
  return isInPeriodShared(item.rawDate, period);
};
