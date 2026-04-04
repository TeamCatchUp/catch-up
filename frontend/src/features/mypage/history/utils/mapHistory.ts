import type { RecentQueryWithSaveStatusResponse } from '@/shared/types/query/api';
import type { DatePeriod } from '@/shared/utils/dateGrouping';
import { getDateGroup, isInPeriod as isInPeriodShared } from '@/shared/utils/dateGrouping';
import { formatFullDate, formatRelativeDate } from '@/shared/utils/formatDate';

import type { HistoryItem } from '../types/historyModel';

/** shared getDateGroup 래퍼 (기존 호출부 호환) */
export const getHistoryGroup = getDateGroup;

/**
 * saved-status API 응답 아이템을 화면용 {@link HistoryItem}으로 변환한다.
 */
export const toHistoryItem = (item: RecentQueryWithSaveStatusResponse): HistoryItem => {
  const rawDate = new Date(item.created_at);

  return {
    id: `${item.id}-${item.session_id}-${item.created_at}`,
    sessionId: item.session_id,
    query: item.content,
    createdAt: item.created_at,
    rawDate,
    fullDate: formatFullDate(item.created_at),
    relativeDate: formatRelativeDate(item.created_at),
    isSaved: item.is_answer_saved,
    answerId: item.answer_id ?? null,
  };
};

/** 히스토리 아이템이 지정된 기간 필터에 해당하는지 판별 */
export const isInPeriod = (item: HistoryItem, period: DatePeriod): boolean => {
  return isInPeriodShared(item.rawDate, period);
};
