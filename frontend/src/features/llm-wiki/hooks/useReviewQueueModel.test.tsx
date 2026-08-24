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

/** 미판정 변경안 블록. 일괄 승인이 판정을 보낼 대상이다 */
const proposedBlock = (blockIndex: number, heading: string) => ({
  block_index: blockIndex,
  block_kind: 'claim_section',
  heading,
  body: `${heading} 새 본문`,
  claim_ids: [],
  proposal_ids: [],
  ontology_version: null,
  block_content_hash: `h-${blockIndex}`,
  narrative: null,
  relation_ids: [],
  sources: [],
  variants: null,
  verdict: null,
  markdown: '',
  change_reason: null,
});

/** 저장된 승인 판정. 이 값이 서면 카드가 접히고 일괄 승인 대상에서 빠진다 */
const blockVerdict = (proposalId: string, blockIndex: number) => ({
  proposal_id: proposalId,
  block_index: blockIndex,
  block_content_hash: `h-${blockIndex}`,
  verdict: 'approved',
  rejection_reason: null,
  chosen_winner_claim_id: null,
  reviewer: '직원10',
  reviewed_at: '2026-08-20T01:00:00Z',
});

const baseBlock = (blockIndex: number, heading: string) => ({
  block_index: blockIndex,
  block_kind: 'claim_section',
  heading,
  body: `${heading} 이전 본문`,
  narrative: null,
  claim_ids: [],
  relation_ids: [],
  sources: [],
});

/**
 * 카드 3장 — 수정·추가·빠진 블록. 빠진 블록은 변경안에 자리가 없어 판정 경로도 없다.
 * 발행 뒤에는 변경 목록이 비어 상세가 "변경 0건"으로 온다.
 */
const detail = (proposalId: string, decided: boolean, approvedBlocks: ReadonlySet<number> = new Set()) => ({
  proposal_id: proposalId,
  status: decided ? 'approved' : 'pending',
  artifact: { id: `art-${proposalId}`, title: '결제 재시도 정책', channel_id: 'ch-1', folder_id: null },
  origin: 'compiled',
  created_at: '2026-08-20T00:00:00Z',
  base_revision_id: 'rev-1',
  contains_conflict: false,
  owners: [],
  can_review: !decided,
  blocks: [proposedBlock(0, '재시도 정책'), proposedBlock(1, 'PG 점검 시간 예외')].map((block) =>
    approvedBlocks.has(block.block_index) ? { ...block, verdict: blockVerdict(proposalId, block.block_index) } : block,
  ),
  layout: [],
  base_blocks: [baseBlock(0, '재시도 정책'), baseBlock(1, '수동 재시도 안내')],
  base_layout: [],
  block_changes: decided
    ? []
    : [
        { change: 'modified', block_index: 0, base_block_index: 0 },
        { change: 'added', block_index: 1, base_block_index: null },
        { change: 'removed', block_index: null, base_block_index: 1 },
      ],
  read_set: { claim_ids: [], proposal_ids: [], relation_ids: [] },
  conflicts: [],
});

/** 발행·기각에 성공한 안건이 큐에서 빠지는 서버. 블록 판정 요청은 자리만 받아 적는다 */
function stubReviewEndpoints(items: readonly ReturnType<typeof queueItem>[]) {
  const dropped = new Set<string>();
  const approved = new Map<string, Set<number>>();
  const verdictCalls: string[] = [];

  server.use(
    http.get('*/api/v1/knowledge-review/queue', () => {
      const rest = items.filter((item) => !dropped.has(item.proposal_id));
      return HttpResponse.json({ items: rest, total: rest.length, limit: 50, offset: 0 });
    }),
    http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) => {
      const proposalId = String(params.proposalId);
      return HttpResponse.json(detail(proposalId, dropped.has(proposalId), approved.get(proposalId) ?? new Set()));
    }),
    http.put('*/api/v1/knowledge-review/queue/:proposalId/blocks/:blockIndex/verdict', ({ params }) => {
      const proposalId = String(params.proposalId);
      verdictCalls.push(String(params.blockIndex));
      approved.set(proposalId, (approved.get(proposalId) ?? new Set()).add(Number(params.blockIndex)));
      return HttpResponse.json({
        proposal_id: proposalId,
        block_index: Number(params.blockIndex),
        block_content_hash: `h-${params.blockIndex}`,
        verdict: 'approved',
        rejection_reason: null,
        chosen_winner_claim_id: null,
        reviewer: '직원10',
        reviewed_at: '2026-08-20T01:00:00Z',
      });
    }),
    http.post('*/api/v1/knowledge-review/queue/:proposalId/publish', ({ params }) => {
      dropped.add(String(params.proposalId));
      return HttpResponse.json({
        proposal_id: String(params.proposalId),
        verdict: 'published',
        revision_id: 'rev-2',
        revision_number: 2,
        blocks_published: 2,
        blocks_rejected: 0,
        contradictions_resolved: 0,
        claims_accepted: 2,
      });
    }),
    http.post('*/api/v1/knowledge-review/artifacts/:proposalId/reject', ({ params }) => {
      dropped.add(String(params.proposalId));
      return HttpResponse.json({
        proposal_id: String(params.proposalId),
        verdict: 'rejected',
        revision_id: null,
        revision_number: null,
        claims_accepted: 0,
      });
    }),
    http.get('*/api/v1/wiki/channels', () => HttpResponse.json({ channels: [] })),
    http.get('*/api/v1/wiki/members', () => HttpResponse.json({ items: [] })),
  );

  return { verdictCalls };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useReviewQueueModel', () => {
  it('전체 승인은 판정 경로가 있는 카드 수만큼 블록 판정을 보낸다 — 빠진 블록은 빠진다', async () => {
    const { verdictCalls } = stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    // 카드는 셋인데 그중 하나는 발행판에서만 빠진 블록이라 보낼 경로가 없다
    await waitFor(() => expect(result.current.entries).toHaveLength(3));

    act(() => result.current.onApproveAll());

    await waitFor(() => expect(verdictCalls).toHaveLength(2));
    expect([...verdictCalls].sort()).toEqual(['0', '1']);

    // 발행은 별도 클릭이다 — 안건이 큐에 남고 발행 바도 열려 있다
    expect(result.current.items).toHaveLength(1);
    expect(result.current.selectedId).toBe(FIRST);
    expect(result.current.publishDisabled).toBe(false);
  });

  it('보낼 카드가 없으면 전체 승인이 요청을 내지 않는다', async () => {
    const { verdictCalls } = stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));

    act(() => result.current.onApproveAll());
    // 다시 읽은 상세가 판정을 물고 오면 보낼 대상이 비어야 한다
    await waitFor(() => expect(result.current.entries.filter((entry) => entry.approved)).toHaveLength(2));

    act(() => result.current.onApproveAll());
    expect(verdictCalls).toHaveLength(2);
  });

  it('발행에 성공하면 다음 안건으로 넘어간다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.selectedId).toBe(FIRST));

    act(() => result.current.onPublish());

    await waitFor(() => expect(result.current.selectedId).toBe(SECOND));
    await waitFor(() => expect(result.current.items).toHaveLength(1));
  });

  it('마지막 안건을 발행하면 이전 안건으로 올라간다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.items).toHaveLength(2));
    act(() => result.current.onSelectItem(SECOND));
    await waitFor(() => expect(result.current.entries).toHaveLength(3));

    act(() => result.current.onPublish());

    await waitFor(() => expect(result.current.selectedId).toBe(FIRST));
  });

  it('하나뿐인 안건을 발행하면 고를 안건이 없어진다 — 빈 안내가 선다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));

    act(() => result.current.onPublish());

    await waitFor(() => expect(result.current.items).toHaveLength(0));
    expect(result.current.selectedId).toBeNull();
  });

  it('전체 반려에 성공하면 다음 안건으로 넘어간다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.selectedId).toBe(FIRST));

    act(() => result.current.onRejectAll('근거 문서가 없습니다'));

    await waitFor(() => expect(result.current.selectedId).toBe(SECOND));
    expect(result.current.rejectDialogOpen).toBe(false);
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
