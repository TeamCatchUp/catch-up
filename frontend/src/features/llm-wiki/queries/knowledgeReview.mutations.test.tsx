import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  REVIEW_TOAST_OPTIONS,
  useRejectReviewProposalMutation,
  useReviewBlockVerdictMutation,
  useReviewPublishMutation,
} from './knowledgeReview.mutations';
import { knowledgeReviewQueries } from './knowledgeReview.queries';
import { wikiQueries } from './wiki.queries';

const apiMock = vi.hoisted(() => ({ post: vi.fn(), put: vi.fn() }));
const toastMock = vi.hoisted(() => vi.fn());

// 실 요청과 sonner 렌더를 막는다 — 여기서 볼 것은 무효화 대상뿐이다
vi.mock('@/shared/api/client', () => ({ default: apiMock }));
vi.mock('@/shared/components/ui/toast', () => ({ toast: toastMock }));

const PROPOSAL_ID = 'pr-1';

/** parseApiError가 읽는 최소 형태의 axios 에러 */
const apiError = (code: string, message: string) => ({
  isAxiosError: true,
  response: { data: { detail: { code, message } } },
});

const createHarness = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const spy = vi.spyOn(client, 'invalidateQueries');

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );

  return { wrapper, invalidatedKeys: () => spy.mock.calls.map(([filters]) => filters?.queryKey) };
};

const detailKey = knowledgeReviewQueries.queueItem(PROPOSAL_ID).queryKey;

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useReviewBlockVerdictMutation', () => {
  const VERDICT_RESPONSE = {
    proposal_id: PROPOSAL_ID,
    block_index: 2,
    block_content_hash: 'h-2',
    verdict: 'approved',
    rejection_reason: null,
    chosen_winner_claim_id: null,
    reviewer: '팀원F',
    reviewed_at: '2026-08-19T09:00:00Z',
  };

  it('블록 자리는 경로로 가고 본문에는 남지 않는다', async () => {
    apiMock.put.mockResolvedValue({ data: VERDICT_RESPONSE });
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useReviewBlockVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ blockIndex: 2, verdict: 'approved', block_content_hash: 'h-2' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock.put).toHaveBeenCalledWith('/api/v1/knowledge-review/queue/pr-1/blocks/2/verdict', {
      verdict: 'approved',
      block_content_hash: 'h-2',
    });
    expect(result.current.data).toEqual(VERDICT_RESPONSE);
  });

  it('성공하면 상세만 다시 읽는다 — 블록 판정으로 큐 줄은 바뀌지 않는다', async () => {
    apiMock.put.mockResolvedValue({ data: VERDICT_RESPONSE });
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewBlockVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ blockIndex: 2, verdict: 'approved', block_content_hash: 'h-2' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([detailKey]);
  });

  it('낡은 지문으로 막히면 서버 문구를 띄우고 상세를 다시 읽는다 — 재조회가 곧 복구다', async () => {
    apiMock.put.mockRejectedValue(apiError('STALE_BLOCK', '다른 검토자가 먼저 판정했어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewBlockVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ blockIndex: 2, verdict: 'approved', block_content_hash: 'stale' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('다른 검토자가 먼저 판정했어요.', REVIEW_TOAST_OPTIONS);
    expect(invalidatedKeys()).toEqual([detailKey]);
  });

  it('낙관적 잠금과 무관한 실패는 문구만 띄우고 캐시를 건드리지 않는다', async () => {
    apiMock.put.mockRejectedValue(apiError('FORBIDDEN', '검토 권한이 없어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewBlockVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ blockIndex: 2, verdict: 'approved', block_content_hash: 'h-2' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('검토 권한이 없어요.', REVIEW_TOAST_OPTIONS);
    expect(invalidatedKeys()).toEqual([]);
  });
});

describe('useReviewPublishMutation', () => {
  const PUBLISH_RESPONSE = {
    proposal_id: PROPOSAL_ID,
    verdict: 'published',
    revision_id: 'rv-9',
    revision_number: 3,
    blocks_published: 2,
    blocks_rejected: 0,
    contradictions_resolved: 0,
    claims_accepted: 4,
  };

  it('발행은 큐 뿌리와 위키 뿌리를 함께 무효화한다 — 줄이 빠지고 문서 상태도 바뀐다', async () => {
    apiMock.post.mockResolvedValue({ data: PUBLISH_RESPONSE });
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewPublishMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ base_revision_id: 'rv-8' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock.post).toHaveBeenCalledWith('/api/v1/knowledge-review/queue/pr-1/publish', {
      base_revision_id: 'rv-8',
    });
    expect(invalidatedKeys()).toEqual([knowledgeReviewQueries.all(), wikiQueries.all()]);
  });

  it('낡은 상태로 막히면 상세만 다시 읽는다 — 뿌리까지 되돌리지 않는다', async () => {
    apiMock.post.mockRejectedValue(apiError('UNDECIDED_BLOCKS', '아직 판정하지 않은 블록이 있어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewPublishMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ base_revision_id: 'rv-8' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('아직 판정하지 않은 블록이 있어요.', REVIEW_TOAST_OPTIONS);
    expect(invalidatedKeys()).toEqual([detailKey]);
  });

  it('그 밖의 실패는 문구만 띄운다', async () => {
    apiMock.post.mockRejectedValue(apiError('FORBIDDEN', '발행 권한이 없어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewPublishMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ base_revision_id: 'rv-8' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('발행 권한이 없어요.', REVIEW_TOAST_OPTIONS);
    expect(invalidatedKeys()).toEqual([]);
  });
});

describe('useRejectReviewProposalMutation', () => {
  const REJECT_RESPONSE = {
    proposal_id: PROPOSAL_ID,
    verdict: 'rejected',
    revision_id: null,
    revision_number: null,
    claims_accepted: 0,
  };

  it('반려는 blocks가 아니라 artifacts 경로로 가고 사유를 실어 보낸다', async () => {
    apiMock.post.mockResolvedValue({ data: REJECT_RESPONSE });
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useRejectReviewProposalMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ reason: '근거가 부족해요.' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock.post).toHaveBeenCalledWith('/api/v1/knowledge-review/artifacts/pr-1/reject', {
      reason: '근거가 부족해요.',
    });
  });

  it('반려도 큐 뿌리와 위키 뿌리를 함께 무효화한다', async () => {
    apiMock.post.mockResolvedValue({ data: REJECT_RESPONSE });
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRejectReviewProposalMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ reason: '근거가 부족해요.' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([knowledgeReviewQueries.all(), wikiQueries.all()]);
  });

  it('실패하면 문구만 띄운다 — 반려에는 낡은 상태 재조회 분기가 없다', async () => {
    apiMock.post.mockRejectedValue(apiError('ALREADY_DECIDED', '이미 판정된 변경안이에요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRejectReviewProposalMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ reason: '근거가 부족해요.' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('이미 판정된 변경안이에요.', REVIEW_TOAST_OPTIONS);
    expect(invalidatedKeys()).toEqual([]);
  });
});
