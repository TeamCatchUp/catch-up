import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  useReviewBlockVerdictMutation,
  useReviewBulkVerdictMutation,
  useReviewPublishMutation,
} from './knowledgeReview.mutations';
import { knowledgeReviewQueries } from './knowledgeReview.queries';
import { wikiQueries } from './wiki.queries';

const reviewApi = vi.hoisted(() => ({
  submitReviewBlockVerdict: vi.fn(),
  publishReviewProposal: vi.fn(),
}));
const toastMock = vi.hoisted(() => vi.fn());

// 실 요청과 sonner 렌더를 막는다 — 여기서 볼 것은 넘기는 인자와 무효화 대상뿐이다
vi.mock('../api/knowledgeReviewRequests', () => reviewApi);
vi.mock('@/shared/components/ui/toast', () => ({ toast: toastMock }));

const PROPOSAL_ID = 'pr-1';
const ARTIFACT_ID = 'ar-1';

/** 판정으로 되돌리는 위키 캐시 — 문서 목록 전부와 그 문서의 발행판뿐이다 */
const artifactListKey = [...wikiQueries.all(), 'artifacts'];
const artifactDetailKey = wikiQueries.artifact(ARTIFACT_ID).queryKey;

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
    reviewApi.submitReviewBlockVerdict.mockResolvedValue(VERDICT_RESPONSE);
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useReviewBlockVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ blockIndex: 2, verdict: 'approved', block_content_hash: 'h-2' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(reviewApi.submitReviewBlockVerdict).toHaveBeenCalledWith(PROPOSAL_ID, 2, {
      verdict: 'approved',
      block_content_hash: 'h-2',
    });
    expect(result.current.data).toEqual(VERDICT_RESPONSE);
  });

  it('성공하면 상세만 다시 읽는다 — 블록 판정으로 큐 줄은 바뀌지 않는다', async () => {
    reviewApi.submitReviewBlockVerdict.mockResolvedValue(VERDICT_RESPONSE);
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewBlockVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ blockIndex: 2, verdict: 'approved', block_content_hash: 'h-2' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([detailKey]);
  });

  it('낡은 지문으로 막히면 서버 문구를 띄우고 상세를 다시 읽는다 — 재조회가 곧 복구다', async () => {
    reviewApi.submitReviewBlockVerdict.mockRejectedValue(apiError('STALE_BLOCK', '다른 검토자가 먼저 판정했어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewBlockVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ blockIndex: 2, verdict: 'approved', block_content_hash: 'stale' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('다른 검토자가 먼저 판정했어요.');
    expect(invalidatedKeys()).toEqual([detailKey]);
  });

  it('낙관적 잠금과 무관한 실패는 문구만 띄우고 캐시를 건드리지 않는다', async () => {
    reviewApi.submitReviewBlockVerdict.mockRejectedValue(apiError('FORBIDDEN', '검토 권한이 없어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewBlockVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ blockIndex: 2, verdict: 'approved', block_content_hash: 'h-2' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('검토 권한이 없어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});

describe('useReviewBulkVerdictMutation', () => {
  const TARGETS = [
    { blockIndex: 0, block_content_hash: 'h-0' },
    { blockIndex: 2, block_content_hash: 'h-2' },
  ];

  it('받은 카드 수만큼 같은 판정을 보낸다', async () => {
    reviewApi.submitReviewBlockVerdict.mockResolvedValue({});
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useReviewBulkVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ targets: TARGETS, verdict: 'approved' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(reviewApi.submitReviewBlockVerdict).toHaveBeenCalledTimes(2);
    expect(reviewApi.submitReviewBlockVerdict).toHaveBeenCalledWith(PROPOSAL_ID, 2, {
      verdict: 'approved',
      block_content_hash: 'h-2',
    });
    expect(result.current.data).toEqual({ requested: 2, failed: 0, message: null });
  });

  it('반려는 전 블록에 같은 사유를 실어 보낸다', async () => {
    reviewApi.submitReviewBlockVerdict.mockResolvedValue({});
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useReviewBulkVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ targets: TARGETS, verdict: 'rejected', rejection_reason: '근거가 부족해요.' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(reviewApi.submitReviewBlockVerdict).toHaveBeenCalledWith(PROPOSAL_ID, 0, {
      verdict: 'rejected',
      rejection_reason: '근거가 부족해요.',
      block_content_hash: 'h-0',
    });
    expect(reviewApi.submitReviewBlockVerdict).toHaveBeenCalledWith(PROPOSAL_ID, 2, {
      verdict: 'rejected',
      rejection_reason: '근거가 부족해요.',
      block_content_hash: 'h-2',
    });
  });

  // 하나가 막혀도 나머지는 서버에 남는다 — 실패 건수와 서버 문구를 소비처로 올린다
  it('일부만 실패해도 성공분을 살리고 첫 실패의 문구를 돌려준다', async () => {
    reviewApi.submitReviewBlockVerdict
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(apiError('STALE_BLOCK', '다른 검토자가 먼저 판정했어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewBulkVerdictMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ targets: TARGETS, verdict: 'approved' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ requested: 2, failed: 1, message: '다른 검토자가 먼저 판정했어요.' });
    expect(invalidatedKeys()).toEqual([detailKey]);
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

  // 채널·구성원·preset(staleTime Infinity)은 판정으로 바뀌지 않는다 — 위키 뿌리를 통째로 되돌리지 않는다
  it('발행은 큐 뿌리와 문서 목록·그 문서 상세만 무효화한다', async () => {
    reviewApi.publishReviewProposal.mockResolvedValue(PUBLISH_RESPONSE);
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewPublishMutation(PROPOSAL_ID, ARTIFACT_ID), { wrapper });

    result.current.mutate({ base_revision_id: 'rv-8' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(reviewApi.publishReviewProposal).toHaveBeenCalledWith(PROPOSAL_ID, { base_revision_id: 'rv-8' });
    expect(invalidatedKeys()).toEqual([knowledgeReviewQueries.all(), artifactListKey, artifactDetailKey]);
  });

  it('문서 id를 모르면 목록만 되돌린다 — 상세는 되돌릴 자리를 못 짚는다', async () => {
    reviewApi.publishReviewProposal.mockResolvedValue(PUBLISH_RESPONSE);
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewPublishMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ base_revision_id: 'rv-8' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([knowledgeReviewQueries.all(), artifactListKey]);
  });

  it('낡은 상태로 막히면 상세만 다시 읽는다 — 뿌리까지 되돌리지 않는다', async () => {
    reviewApi.publishReviewProposal.mockRejectedValue(
      apiError('UNDECIDED_BLOCKS', '아직 판정하지 않은 블록이 있어요.'),
    );
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewPublishMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ base_revision_id: 'rv-8' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('아직 판정하지 않은 블록이 있어요.');
    expect(invalidatedKeys()).toEqual([detailKey]);
  });

  it('그 밖의 실패는 문구만 띄운다', async () => {
    reviewApi.publishReviewProposal.mockRejectedValue(apiError('FORBIDDEN', '발행 권한이 없어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useReviewPublishMutation(PROPOSAL_ID), { wrapper });

    result.current.mutate({ base_revision_id: 'rv-8' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('발행 권한이 없어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});
