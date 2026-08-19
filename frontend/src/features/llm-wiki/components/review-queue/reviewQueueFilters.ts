import { startOfDay, subDays } from 'date-fns';

import type { ReviewQueueItemDto, ReviewQueueParams } from '../../api/knowledgeReviewDto';

/** 대기 기간 축. 단일 선택이고 "이전"은 "7일 이내"의 여집합이다. */
export type ReviewQueueWaitingId = 'all' | 'today' | 'within-7d' | 'before';

export const REVIEW_QUEUE_WAITING_OPTIONS: readonly { id: ReviewQueueWaitingId; label: string }[] = [
  { id: 'all', label: '전체' },
  { id: 'today', label: '오늘' },
  { id: 'within-7d', label: '7일 이내' },
  { id: 'before', label: '이전' },
];

/** 큐 목록에 걸린 필터. 채널·담당자는 다중 선택이고 대기 기간은 단일 선택이다. */
export interface ReviewQueueFilterState {
  channelIds: readonly string[];
  /** 담당자 옵션 id = user_id 문자열 */
  assigneeIds: readonly string[];
  waitingId: ReviewQueueWaitingId;
}

export const INITIAL_REVIEW_QUEUE_FILTER_STATE: ReviewQueueFilterState = {
  channelIds: [],
  assigneeIds: [],
  waitingId: 'all',
};

export function isReviewQueueFiltered(state: ReviewQueueFilterState): boolean {
  return state.channelIds.length > 0 || state.assigneeIds.length > 0 || state.waitingId !== 'all';
}

/** 7일 이내와 이전을 가르는 경계. 사용자가 고르는 것은 날짜라 하루 단위로 자른다 */
const waitingBoundary = (now: Date) => subDays(startOfDay(now), 6);

function resolveWaitingRange(waitingId: ReviewQueueWaitingId, now: Date): ReviewQueueParams {
  switch (waitingId) {
    case 'today':
      return { created_after: startOfDay(now).toISOString() };
    case 'within-7d':
      return { created_after: waitingBoundary(now).toISOString() };
    case 'before':
      return { created_before: waitingBoundary(now).toISOString() };
    case 'all':
      return {};
  }
}

interface ReviewQueuePaging {
  limit: number;
  offset: number;
  /** 대기 기간 경계의 기준 시각 */
  now: Date;
}

/**
 * 필터 상태 → 큐 조회 파라미터. 서버는 채널·담당자를 하나씩만 받으므로
 * 2개 이상 고른 축은 파라미터로 나가지 않고 받은 쪽에서 좁힌다.
 */
export function buildReviewQueueParams(state: ReviewQueueFilterState, paging: ReviewQueuePaging): ReviewQueueParams {
  const ownerUserIds = toOwnerUserIds(state.assigneeIds);

  return {
    limit: paging.limit,
    offset: paging.offset,
    ...resolveWaitingRange(state.waitingId, paging.now),
    ...(state.channelIds.length === 1 ? { channel_id: state.channelIds[0] } : {}),
    ...(ownerUserIds.length === 1 ? { owner_user_id: ownerUserIds[0] } : {}),
  };
}

/** 담당자 옵션 id → user_id. 숫자가 아닌 id는 담당자로 세지 않는다 */
function toOwnerUserIds(assigneeIds: readonly string[]): number[] {
  return assigneeIds.map(Number).filter(Number.isInteger);
}

/** 서버가 표현하지 못하는 다중 선택분. 2개 이상 고른 축에만 값이 있다 */
export function resolveClientQueueFilter(state: ReviewQueueFilterState): {
  channelIds: readonly string[];
  ownerUserIds: readonly number[];
} {
  const ownerUserIds = toOwnerUserIds(state.assigneeIds);

  return {
    channelIds: state.channelIds.length > 1 ? state.channelIds : [],
    ownerUserIds: ownerUserIds.length > 1 ? ownerUserIds : [],
  };
}

/** 다중 선택분을 응답 위에서 좁힌다. 빈 축은 거르지 않는다 — 빈 선택으로 목록을 비우지 않는다 */
export function filterQueueItems(
  items: readonly ReviewQueueItemDto[],
  filter: { channelIds: readonly string[]; ownerUserIds: readonly number[] },
): readonly ReviewQueueItemDto[] {
  return items.filter((item) => {
    const channelMatched =
      filter.channelIds.length === 0 ||
      (item.artifact.channel_id !== null && filter.channelIds.includes(item.artifact.channel_id));
    const ownerMatched =
      filter.ownerUserIds.length === 0 || item.owners.some((owner) => filter.ownerUserIds.includes(owner.user_id));

    return channelMatched && ownerMatched;
  });
}
