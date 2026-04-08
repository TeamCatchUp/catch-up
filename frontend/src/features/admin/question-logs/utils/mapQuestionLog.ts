import type { RecentQueryWithSaveStatusResponse } from '@/shared/types/query/api';
import { formatFullDate, formatRelativeTime } from '@/shared/utils/formatDate';

import type { QuestionLogItem } from '../types/questionLogModel';

/** API 응답 → QuestionLogItem UI 모델 변환 */
export const toQuestionLogItem = (item: RecentQueryWithSaveStatusResponse): QuestionLogItem => ({
  id: `${item.id}-${item.session_id}`,
  messageId: item.id,
  sessionId: item.session_id,
  query: item.content,
  createdAt: item.created_at,
  rawDate: new Date(item.created_at),
  fullDate: formatFullDate(item.created_at),
  relativeDate: formatRelativeTime(item.created_at),
  isSaved: item.is_answer_saved,
  answerId: item.answer_id ?? null,
});
