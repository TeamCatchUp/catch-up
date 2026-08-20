import { hashKey, QueryClient } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReviewProposalDetailDto, ReviewQueuePageDto, ReviewQueueParams } from '../api/knowledgeReviewDto';
import { fetchReviewQueue, fetchReviewQueueItem } from '../api/knowledgeReviewRequests';
import { knowledgeReviewQueries } from './knowledgeReview.queries';

// 실 요청을 막고 queryFn이 fetcher에 넘기는 인자만 본다
vi.mock('../api/knowledgeReviewRequests', () => ({
  fetchReviewQueue: vi.fn(),
  fetchReviewQueueItem: vi.fn(),
}));

const QUEUE_PAGE: ReviewQueuePageDto = { items: [], total: 0, limit: 50, offset: 0 };
const PROPOSAL_DETAIL: ReviewProposalDetailDto = {
  proposal_id: 'pr-1',
  status: 'pending',
  artifact: { id: 'af-1', title: '결제 실패 대응 가이드', channel_id: 'ch-1', folder_id: 'fd-1' },
  origin: 'compiled',
  created_at: '2026-08-19T09:00:00Z',
  base_revision_id: 'rv-8',
  contains_conflict: false,
  owners: [],
  can_review: true,
  blocks: [],
  base_blocks: [],
  block_changes: [],
  read_set: { claim_ids: [], proposal_ids: [], relation_ids: [] },
  conflicts: [],
};

/** 캐시가 빈 클라이언트. staleTime 때문에 두 번째 호출이 fetcher를 건너뛰는 것을 막는다 */
const freshClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchReviewQueue).mockResolvedValue(QUEUE_PAGE);
  vi.mocked(fetchReviewQueueItem).mockResolvedValue(PROPOSAL_DETAIL);
});

describe('knowledgeReviewQueries 키 뿌리', () => {
  it('뿌리는 ["llm-wiki", "knowledge-review"]다 — 위키 쪽과 앞단을 공유한다', () => {
    expect(knowledgeReviewQueries.all()).toEqual(['llm-wiki', 'knowledge-review']);
  });

  it('큐 목록과 상세가 모두 그 뿌리 아래로 들어간다', () => {
    expect(knowledgeReviewQueries.queue().queryKey.slice(0, 2)).toEqual(['llm-wiki', 'knowledge-review']);
    expect(knowledgeReviewQueries.queueItem('pr-1').queryKey.slice(0, 2)).toEqual(['llm-wiki', 'knowledge-review']);
  });

  it('목록과 상세는 다른 자리다', () => {
    expect(hashKey(knowledgeReviewQueries.queue().queryKey)).not.toBe(
      hashKey(knowledgeReviewQueries.queueItem('pr-1').queryKey),
    );
  });
});

describe('knowledgeReviewQueries.queue 키', () => {
  it('같은 파라미터는 같은 캐시 자리를 가리킨다', () => {
    const first = knowledgeReviewQueries.queue({ channel_id: 'ch-1', limit: 20 }).queryKey;
    const second = knowledgeReviewQueries.queue({ channel_id: 'ch-1', limit: 20 }).queryKey;

    expect(first).toEqual(second);
    expect(hashKey(first)).toBe(hashKey(second));
  });

  it('프로퍼티 순서가 달라도 같은 자리다 — 해시가 키를 정렬해 직렬화한다', () => {
    const declared = knowledgeReviewQueries.queue({ channel_id: 'ch-1', limit: 20, offset: 20 }).queryKey;
    const shuffled = knowledgeReviewQueries.queue({ offset: 20, limit: 20, channel_id: 'ch-1' }).queryKey;

    expect(hashKey(declared)).toBe(hashKey(shuffled));
  });

  it('필터가 다르면 다른 자리다', () => {
    const base = knowledgeReviewQueries.queue({ channel_id: 'ch-1' }).queryKey;

    expect(hashKey(base)).not.toBe(hashKey(knowledgeReviewQueries.queue({ channel_id: 'ch-2' }).queryKey));
    expect(hashKey(base)).not.toBe(
      hashKey(knowledgeReviewQueries.queue({ channel_id: 'ch-1', contains_conflict: true }).queryKey),
    );
    expect(hashKey(base)).not.toBe(
      hashKey(knowledgeReviewQueries.queue({ channel_id: 'ch-1', owner_user_id: 7 }).queryKey),
    );
  });

  it('페이지가 다르면 다른 자리다', () => {
    const first = knowledgeReviewQueries.queue({ limit: 50, offset: 0 }).queryKey;

    expect(hashKey(first)).not.toBe(hashKey(knowledgeReviewQueries.queue({ limit: 50, offset: 50 }).queryKey));
    expect(hashKey(first)).not.toBe(hashKey(knowledgeReviewQueries.queue({ limit: 20, offset: 0 }).queryKey));
  });

  it('파라미터를 생략하면 빈 객체가 실린다', () => {
    expect(knowledgeReviewQueries.queue().queryKey).toEqual(['llm-wiki', 'knowledge-review', 'queue', {}]);
  });

  it('큐 목록을 무효화해도 상세는 그대로다 — 판정 화면이 열려 있는 동안 목록 갱신이 상세를 다시 읽지 않는다', () => {
    const client = freshClient();
    const listKey = knowledgeReviewQueries.queue().queryKey;
    const itemKey = knowledgeReviewQueries.queueItem('pr-1').queryKey;
    client.setQueryData([...listKey], QUEUE_PAGE);
    client.setQueryData([...itemKey], PROPOSAL_DETAIL);

    client.invalidateQueries({ queryKey: listKey });

    expect(client.getQueryState([...listKey])?.isInvalidated).toBe(true);
    expect(client.getQueryState([...itemKey])?.isInvalidated).toBe(false);
  });

  it('뿌리를 무효화하면 목록과 상세가 함께 걸린다 — 발행·반려가 쓰는 경로다', () => {
    const client = freshClient();
    const listKey = knowledgeReviewQueries.queue({ channel_id: 'ch-1' }).queryKey;
    const itemKey = knowledgeReviewQueries.queueItem('pr-1').queryKey;
    client.setQueryData([...listKey], QUEUE_PAGE);
    client.setQueryData([...itemKey], PROPOSAL_DETAIL);

    client.invalidateQueries({ queryKey: knowledgeReviewQueries.all() });

    expect(client.getQueryState([...listKey])?.isInvalidated).toBe(true);
    expect(client.getQueryState([...itemKey])?.isInvalidated).toBe(true);
  });
});

describe('knowledgeReviewQueries.queueItem 키와 enabled', () => {
  it('변경안이 다르면 다른 자리다', () => {
    expect(hashKey(knowledgeReviewQueries.queueItem('pr-1').queryKey)).not.toBe(
      hashKey(knowledgeReviewQueries.queueItem('pr-2').queryKey),
    );
  });

  it('proposalId가 비면 조회하지 않는다', () => {
    expect(knowledgeReviewQueries.queueItem('').enabled).toBe(false);
  });

  it('proposalId가 있으면 조회한다 — 결정 권한은 응답의 can_review로 오므로 여기서 잠그지 않는다', () => {
    expect(knowledgeReviewQueries.queueItem('pr-1').enabled).toBe(true);
  });

  it('큐 목록에는 잠금 조건이 없다', () => {
    expect(knowledgeReviewQueries.queue().enabled).toBeUndefined();
  });
});

describe('knowledgeReviewQueries 신선도', () => {
  it('큐는 문서 목록보다 짧게 잡힌다 — 판정으로 줄이 빠지는 목록이다', () => {
    expect(knowledgeReviewQueries.queue().staleTime).toBe(15_000);
    expect(knowledgeReviewQueries.queueItem('pr-1').staleTime).toBe(15_000);
  });
});

describe('knowledgeReviewQueries queryFn', () => {
  it('큐는 필터·페이지를 그대로 fetcher에 넘긴다', async () => {
    const params: ReviewQueueParams = {
      contains_conflict: true,
      channel_id: 'ch-1',
      owner_user_id: 7,
      created_after: '2026-08-01T00:00:00Z',
      created_before: '2026-08-19T00:00:00Z',
      limit: 20,
      offset: 40,
    };

    await freshClient().fetchQuery(knowledgeReviewQueries.queue(params));

    expect(fetchReviewQueue).toHaveBeenCalledWith(params, expect.any(AbortSignal));
  });

  it('파라미터 없는 큐는 빈 객체를 넘긴다', async () => {
    await freshClient().fetchQuery(knowledgeReviewQueries.queue());

    expect(fetchReviewQueue).toHaveBeenCalledWith({}, expect.any(AbortSignal));
  });

  it('상세는 proposalId를 경로 인자로 넘긴다', async () => {
    await freshClient().fetchQuery(knowledgeReviewQueries.queueItem('pr-1'));

    expect(fetchReviewQueueItem).toHaveBeenCalledWith('pr-1', expect.any(AbortSignal));
  });
});
