import { startOfDay } from 'date-fns';
import { describe, expect, it } from 'vitest';

import type { ReviewQueueItemDto } from '../../api/knowledgeReviewDto';
import {
  buildReviewQueueParams,
  filterQueueItems,
  INITIAL_REVIEW_QUEUE_FILTER_STATE,
  isReviewQueueFiltered,
  resolveClientQueueFilter,
} from './reviewQueueFilters';

const NOW = new Date('2026-08-19T09:30:00.000Z');
const PAGING = { limit: 50, offset: 0, now: NOW };

const item = (overrides: Partial<ReviewQueueItemDto> = {}): ReviewQueueItemDto => ({
  proposal_id: 'p-1',
  status: 'pending',
  artifact: { id: 'a-1', title: '결제 재시도', channel_id: 'ch-billing', folder_id: null },
  summary: '재시도 한도 변경',
  origin: 'compiled',
  contains_conflict: false,
  created_at: '2026-08-18T00:00:00.000Z',
  owners: [{ user_id: 1, display_name: '팀원F', profile_image_url: null }],
  can_review: true,
  ...overrides,
});

describe('buildReviewQueueParams', () => {
  it('필터가 없으면 쪽 파라미터만 실린다', () => {
    expect(buildReviewQueueParams(INITIAL_REVIEW_QUEUE_FILTER_STATE, PAGING)).toEqual({ limit: 50, offset: 0 });
  });

  it('채널·담당자를 하나씩 고르면 서버 파라미터가 된다', () => {
    const params = buildReviewQueueParams(
      { channelIds: ['ch-billing'], assigneeIds: ['7'], waitingId: 'all' },
      PAGING,
    );

    expect(params).toMatchObject({ channel_id: 'ch-billing', owner_user_id: 7 });
  });

  it('둘 이상 고른 축은 서버로 나가지 않는다 — 서버가 하나씩만 받는다', () => {
    const params = buildReviewQueueParams(
      { channelIds: ['ch-a', 'ch-b'], assigneeIds: ['7', '8'], waitingId: 'all' },
      PAGING,
    );

    expect(params).not.toHaveProperty('channel_id');
    expect(params).not.toHaveProperty('owner_user_id');
  });

  it('대기 기간 "7일 이내"와 "이전"은 같은 경계의 여집합이다', () => {
    const within = buildReviewQueueParams({ ...INITIAL_REVIEW_QUEUE_FILTER_STATE, waitingId: 'within-7d' }, PAGING);
    const before = buildReviewQueueParams({ ...INITIAL_REVIEW_QUEUE_FILTER_STATE, waitingId: 'before' }, PAGING);

    expect(within.created_after).toBe(before.created_before);
    expect(within).not.toHaveProperty('created_before');
    expect(before).not.toHaveProperty('created_after');
  });

  it('"오늘"은 시각이 아니라 하루 경계로 자른다', () => {
    const params = buildReviewQueueParams({ ...INITIAL_REVIEW_QUEUE_FILTER_STATE, waitingId: 'today' }, PAGING);
    expect(params.created_after).toBe(startOfDay(NOW).toISOString());
    expect(params.created_after).not.toBe(NOW.toISOString());
  });
});

describe('resolveClientQueueFilter', () => {
  it('하나만 고른 축은 클라이언트에 남기지 않는다 (서버가 이미 걸렀다)', () => {
    const filter = resolveClientQueueFilter({ channelIds: ['ch-a'], assigneeIds: ['7'], waitingId: 'all' });
    expect(filter).toEqual({ channelIds: [], ownerUserIds: [] });
  });

  it('둘 이상 고른 축만 클라이언트로 넘어온다', () => {
    const filter = resolveClientQueueFilter({ channelIds: ['ch-a', 'ch-b'], assigneeIds: ['7', '8'], waitingId: 'all' });
    expect(filter).toEqual({ channelIds: ['ch-a', 'ch-b'], ownerUserIds: [7, 8] });
  });
});

describe('filterQueueItems', () => {
  it('빈 축은 거르지 않는다', () => {
    const items = [item()];
    expect(filterQueueItems(items, { channelIds: [], ownerUserIds: [] })).toEqual(items);
  });

  it('채널·담당자 축은 함께 걸린다 (AND)', () => {
    const items = [
      item({ proposal_id: 'p-1' }),
      item({ proposal_id: 'p-2', artifact: { id: 'a-2', title: null, channel_id: 'ch-other', folder_id: null } }),
      item({ proposal_id: 'p-3', owners: [{ user_id: 9, display_name: '남궁현', profile_image_url: null }] }),
    ];

    const filtered = filterQueueItems(items, { channelIds: ['ch-billing', 'ch-x'], ownerUserIds: [1, 2] });
    expect(filtered.map((row) => row.proposal_id)).toEqual(['p-1']);
  });

  it('미분류 문서(channel_id 없음)는 채널 축에 걸리면 빠진다', () => {
    const items = [item({ artifact: { id: 'a-1', title: null, channel_id: null, folder_id: null } })];
    expect(filterQueueItems(items, { channelIds: ['ch-a', 'ch-b'], ownerUserIds: [] })).toHaveLength(0);
  });
});

describe('isReviewQueueFiltered', () => {
  it('초기 상태는 필터가 걸리지 않은 것이다', () => {
    expect(isReviewQueueFiltered(INITIAL_REVIEW_QUEUE_FILTER_STATE)).toBe(false);
    expect(isReviewQueueFiltered({ ...INITIAL_REVIEW_QUEUE_FILTER_STATE, waitingId: 'today' })).toBe(true);
  });
});
