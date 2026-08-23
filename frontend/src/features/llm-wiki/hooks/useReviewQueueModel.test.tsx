import type { PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { server } from '@/test/msw/server';

import { useReviewQueueModel } from './useReviewQueueModel';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/shared/components/ui/toast', () => ({ toast: vi.fn() }));

const FIRST = 'prop-first';
const SECOND = 'prop-second';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

const queueItem = (proposalId: string, title: string) => ({
  proposal_id: proposalId,
  status: 'pending',
  artifact: { id: `art-${proposalId}`, title, channel_id: 'ch-1', folder_id: null },
  summary: `${title} 요약`,
  origin: 'compiled',
  contains_conflict: false,
  created_at: '2026-08-20T00:00:00Z',
  owners: [],
  can_review: true,
});

/** 판정이 끝난 블록 하나. 발행 직전에는 전 블록에 이 판정이 서 있다 */
const decidedBlock = () => ({
  block_index: 0,
  block_kind: 'claim_section',
  heading: '재시도 정책',
  body: '3회까지 재시도한다.',
  claim_ids: [],
  proposal_ids: [],
  ontology_version: null,
  block_content_hash: 'h-0',
  narrative: null,
  relation_ids: [],
  sources: [],
  variants: null,
  verdict: {
    proposal_id: FIRST,
    block_index: 0,
    block_content_hash: 'h-0',
    verdict: 'approved',
    rejection_reason: null,
    chosen_winner_claim_id: null,
    reviewer: '직원10',
    reviewed_at: '2026-08-20T01:00:00Z',
  },
  markdown: '',
  change_reason: null,
});

const baseBlock = () => ({
  block_index: 0,
  block_kind: 'claim_section',
  heading: '재시도 정책',
  body: '1회 재시도한다.',
  narrative: null,
  claim_ids: [],
  relation_ids: [],
  sources: [],
});

/** 발행 뒤에는 변경 목록이 비어 상세가 "변경 0건"으로 온다 */
const detail = (proposalId: string, published: boolean) => ({
  proposal_id: proposalId,
  status: published ? 'approved' : 'pending',
  artifact: { id: `art-${proposalId}`, title: '결제 재시도 정책', channel_id: 'ch-1', folder_id: null },
  origin: 'compiled',
  created_at: '2026-08-20T00:00:00Z',
  base_revision_id: 'rev-1',
  contains_conflict: false,
  owners: [],
  can_review: !published,
  blocks: [decidedBlock()],
  layout: [],
  base_blocks: [baseBlock()],
  base_layout: [],
  block_changes: published ? [] : [{ change: 'modified', block_index: 0, base_block_index: 0 }],
  read_set: { claim_ids: [], proposal_ids: [], relation_ids: [] },
  conflicts: [],
});

/** 발행 성공 뒤 큐에서 줄이 빠지는 서버. 상세도 변경 0건으로 바뀐다 */
function stubReviewEndpoints(items: readonly ReturnType<typeof queueItem>[]) {
  let published = false;

  server.use(
    http.get('*/api/v1/knowledge-review/queue', () =>
      HttpResponse.json({
        items: published ? [] : items,
        total: published ? 0 : items.length,
        limit: 50,
        offset: 0,
      }),
    ),
    http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
      HttpResponse.json(detail(String(params.proposalId), published)),
    ),
    http.post('*/api/v1/knowledge-review/queue/:proposalId/publish', () => {
      published = true;
      return HttpResponse.json({
        proposal_id: FIRST,
        verdict: 'published',
        revision_id: 'rev-2',
        revision_number: 2,
        blocks_published: 1,
        blocks_rejected: 0,
        contradictions_resolved: 0,
        claims_accepted: 1,
      });
    }),
    http.get('*/api/v1/wiki/channels', () => HttpResponse.json({ channels: [] })),
    http.get('*/api/v1/wiki/members', () => HttpResponse.json({ items: [] })),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useReviewQueueModel', () => {
  it('발행에 성공하면 판정 화면이 그대로 남는다 — 줄이 빠져도 빈 안내로 넘어가지 않는다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(1));

    act(() => result.current.onPublish());

    await waitFor(() => expect(result.current.detailRetained).toBe(true));
    // 큐에서 줄이 빠져도 고른 안건과 카드가 남는다 — 변경 0건 상세로 갈아타지 않는다
    await waitFor(() => expect(result.current.items).toHaveLength(0));
    expect(result.current.selectedId).toBe(FIRST);
    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].approved).toBe(true);

    // 판정이 끝난 화면이라 판정·발행 진입점이 거둬진다
    expect(result.current.canReview).toBe(false);
    expect(result.current.publishDisabled).toBe(true);
  });

  it('붙잡아 둔 판정이 없으면 목록이 빈 뒤 상세를 지키지 않는다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.selectedId).toBe(FIRST));
    expect(result.current.detailRetained).toBe(false);
  });

  it('거르기를 바꿔도 보던 안건이 새 목록에 있으면 선택이 남는다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.items).toHaveLength(2));

    act(() => result.current.onSelectItem(SECOND));
    expect(result.current.selectedId).toBe(SECOND);

    act(() => result.current.onFiltersChange({ ...result.current.filters, waitingId: 'within-7d' }));

    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(result.current.selectedId).toBe(SECOND);
  });

  it('artifactId 힌트가 있으면 그 문서의 안건이 골라진다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    const { result } = renderHook(() => useReviewQueueModel({ preselectArtifactId: `art-${SECOND}` }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.selectedId).toBe(SECOND));
  });

  it('힌트와 맞는 안건이 없으면(이미 처리됨) 기본 선택이 그대로 선다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    const { result } = renderHook(() => useReviewQueueModel({ preselectArtifactId: 'art-gone' }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(result.current.selectedId).toBe(FIRST);
  });

  it('힌트는 한 번만 먹는다 — 목록이 다시 와도 그 뒤의 선택을 덮지 않는다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    const { result } = renderHook(() => useReviewQueueModel({ preselectArtifactId: `art-${SECOND}` }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.selectedId).toBe(SECOND));
    act(() => result.current.onSelectItem(FIRST));

    // 거르기를 바꾸면 큐를 다시 부른다 — 그때 힌트가 되살아나면 안 된다
    act(() => result.current.onFiltersChange({ ...result.current.filters, waitingId: 'within-7d' }));

    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(result.current.selectedId).toBe(FIRST);
  });

  it('힌트는 목록이 처음 온 순간에만 풀린다 — 뒤늦게 나타난 안건에는 먹지 않는다', async () => {
    let requestCount = 0;
    server.use(
      http.get('*/api/v1/knowledge-review/queue', () => {
        requestCount += 1;
        // 둘째 요청부터 힌트와 맞는 안건이 목록에 들어온다
        const items =
          requestCount === 1
            ? [queueItem(FIRST, '결제 재시도 정책')]
            : [queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')];
        return HttpResponse.json({ items, total: items.length, limit: 50, offset: 0 });
      }),
      http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
        HttpResponse.json(detail(String(params.proposalId), false)),
      ),
      http.get('*/api/v1/wiki/channels', () => HttpResponse.json({ channels: [] })),
      http.get('*/api/v1/wiki/members', () => HttpResponse.json({ items: [] })),
    );

    const { result } = renderHook(() => useReviewQueueModel({ preselectArtifactId: `art-${SECOND}` }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.items).toHaveLength(1));
    expect(result.current.selectedId).toBe(FIRST);

    act(() => result.current.onFiltersChange({ ...result.current.filters, waitingId: 'within-7d' }));

    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(result.current.selectedId).toBe(FIRST);
  });

  it('거른 결과에 보던 안건이 없으면 첫 줄로 내려온다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.items).toHaveLength(2));
    act(() => result.current.onSelectItem(SECOND));

    // 채널을 둘 이상 고르면 응답 위에서 좁힌다 — 둘째 안건은 그 채널에 없어 목록에서 빠진다
    act(() => result.current.onFiltersChange({ ...result.current.filters, channelIds: ['ch-other', 'ch-another'] }));

    await waitFor(() => expect(result.current.items).toHaveLength(0));
    expect(result.current.selectedId).toBeNull();
  });
});
