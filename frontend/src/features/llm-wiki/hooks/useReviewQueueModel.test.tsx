import type { PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { toast } from '@/shared/components/ui/toast';
import { server } from '@/test/msw/server';

import { wikiQueries } from '../queries/wiki.queries';
import { useReviewQueueModel } from './useReviewQueueModel';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/shared/components/ui/toast', () => ({ toast: vi.fn() }));

const toastMock = vi.mocked(toast);

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

/** 저장된 블록 판정. 이 값이 서면 카드가 접히고 일괄 판정 대상에서 빠진다 */
const blockVerdict = (proposalId: string, blockIndex: number, verdict = 'approved', reason: string | null = null) => ({
  proposal_id: proposalId,
  block_index: blockIndex,
  block_content_hash: `h-${blockIndex}`,
  verdict,
  rejection_reason: reason,
  chosen_winner_claim_id: null,
  reviewer: '직원10',
  reviewed_at: '2026-08-20T01:00:00Z',
});

/** 스텁 서버가 블록마다 받아 적는 판정 */
interface SavedVerdict {
  verdict: string;
  reason: string | null;
}

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
const detail = (
  proposalId: string,
  decided: boolean,
  decidedBlocks: ReadonlyMap<number, SavedVerdict> = new Map(),
) => ({
  proposal_id: proposalId,
  status: decided ? 'approved' : 'pending',
  artifact: { id: `art-${proposalId}`, title: '결제 재시도 정책', channel_id: 'ch-1', folder_id: null },
  origin: 'compiled',
  created_at: '2026-08-20T00:00:00Z',
  base_revision_id: 'rev-1',
  contains_conflict: false,
  owners: [],
  can_review: !decided,
  blocks: [proposedBlock(0, '재시도 정책'), proposedBlock(1, 'PG 점검 시간 예외')].map((block) => {
    const saved = decidedBlocks.get(block.block_index);
    return saved
      ? { ...block, verdict: blockVerdict(proposalId, block.block_index, saved.verdict, saved.reason) }
      : block;
  }),
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

/** 발행에 성공한 안건이 큐에서 빠지는 서버. 블록 판정 요청은 자리와 판정 본문을 받아 적는다 */
function stubReviewEndpoints(items: readonly ReturnType<typeof queueItem>[]) {
  const dropped = new Set<string>();
  const decided = new Map<string, Map<number, SavedVerdict>>();
  const verdictCalls: { proposalId: string; blockIndex: string; verdict: string; reason: string | null }[] = [];

  server.use(
    http.get('*/api/v1/knowledge-review/queue', () => {
      const rest = items.filter((item) => !dropped.has(item.proposal_id));
      return HttpResponse.json({ items: rest, total: rest.length, limit: 50, offset: 0 });
    }),
    http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) => {
      const proposalId = String(params.proposalId);
      return HttpResponse.json(detail(proposalId, dropped.has(proposalId), decided.get(proposalId) ?? new Map()));
    }),
    http.put('*/api/v1/knowledge-review/queue/:proposalId/blocks/:blockIndex/verdict', async ({ params, request }) => {
      const proposalId = String(params.proposalId);
      const blockIndex = Number(params.blockIndex);
      const body = (await request.json()) as { verdict: string; rejection_reason?: string | null };
      const saved = { verdict: body.verdict, reason: body.rejection_reason ?? null };
      verdictCalls.push({
        proposalId,
        blockIndex: String(params.blockIndex),
        verdict: saved.verdict,
        reason: saved.reason,
      });
      decided.set(proposalId, (decided.get(proposalId) ?? new Map()).set(blockIndex, saved));
      return HttpResponse.json(blockVerdict(proposalId, blockIndex, saved.verdict, saved.reason));
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
    http.get('*/api/v1/wiki/channels', () => HttpResponse.json({ channels: [] })),
    http.get('*/api/v1/wiki/members', () => HttpResponse.json({ items: [] })),
    http.get('*/api/v1/auth/me', () =>
      HttpResponse.json({ user_id: 99, name: '검토자', email: 'reviewer@catchup.dev', role: 'user', status: 'active' }),
    ),
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
    expect(verdictCalls.map((call) => call.blockIndex).sort()).toEqual(['0', '1']);
    expect(verdictCalls.every((call) => call.verdict === 'approved')).toBe(true);

    // 발행은 별도 클릭이다 — 안건이 큐에 남고, 전 카드가 판정돼 발행 바가 열린다
    expect(result.current.items).toHaveLength(1);
    expect(result.current.selectedId).toBe(FIRST);
    await waitFor(() => expect(result.current.publishDisabled).toBe(false));
  });

  it('전체 반려는 이미 승인된 카드도 반려로 덮는다', async () => {
    const { verdictCalls } = stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));

    act(() => result.current.onApproveAll());
    await waitFor(() => expect(result.current.entries.filter((entry) => entry.approved)).toHaveLength(2));

    act(() => result.current.onRejectDialogOpenChange(true));
    act(() => result.current.onRejectAll('근거 문서가 없습니다'));

    // 판정 경로가 있는 두 카드에 다시 나가 승인이 반려로 뒤집힌다
    await waitFor(() => expect(verdictCalls).toHaveLength(4));
    expect(verdictCalls.slice(2).every((call) => call.verdict === 'rejected')).toBe(true);
    await waitFor(() => expect(result.current.entries.filter((entry) => entry.rejected)).toHaveLength(2));
    expect(result.current.entries.filter((entry) => entry.approved)).toHaveLength(0);
  });

  it('전체 승인은 이미 승인된 카드를 빼고 보낸다 — 반려된 카드만 승인으로 뒤집힌다', async () => {
    const { verdictCalls } = stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));

    // 블록 0은 미리 승인, 블록 1은 미리 반려해 둔다
    act(() => result.current.onApproveBlock(result.current.entries[0]));
    await waitFor(() => expect(result.current.entries.filter((entry) => entry.approved)).toHaveLength(1));
    act(() => result.current.onRejectBlock?.(result.current.entries[1]));
    act(() => result.current.onRejectBlockSubmit?.('근거 문서가 없습니다'));
    await waitFor(() => expect(result.current.entries.filter((entry) => entry.rejected)).toHaveLength(1));

    act(() => result.current.onApproveAll());

    // 반려됐던 블록 1만 다시 나간다 — 이미 승인된 블록 0의 판정 기록(검토자·시각)은 덮이지 않는다
    await waitFor(() => expect(result.current.entries.filter((entry) => entry.approved)).toHaveLength(2));
    expect(verdictCalls).toHaveLength(3);
    expect(verdictCalls[2]).toMatchObject({ blockIndex: '1', verdict: 'approved' });
  });

  it('미판정 카드가 남으면 발행이 잠기고 전 카드를 판정하면 열린다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));
    expect(result.current.publishDisabled).toBe(true);

    act(() => result.current.onApproveBlock(result.current.entries[0]));
    // 빠진 블록은 판정 경로가 없어 세지 않는다 — 아직 한 카드가 남았다
    await waitFor(() => expect(result.current.entries.filter((entry) => entry.approved)).toHaveLength(1));
    expect(result.current.publishDisabled).toBe(true);

    act(() => result.current.onApproveAll());
    await waitFor(() => expect(result.current.publishDisabled).toBe(false));
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

  it('전 블록 반려로 종결되면 열기 없는 안내 토스트가 뜬다 — 새 판이 없다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.post('*/api/v1/knowledge-review/queue/:proposalId/publish', ({ params }) =>
        HttpResponse.json({
          proposal_id: params.proposalId,
          verdict: 'rejected',
          revision_id: null,
          revision_number: null,
          blocks_published: 0,
          blocks_rejected: 2,
          contradictions_resolved: 0,
          claims_accepted: 0,
        }),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));
    act(() => result.current.onPublish());

    await waitFor(() => expect(toastMock).toHaveBeenCalledWith('모든 변경을 반려해 문서를 바꾸지 않고 종결했습니다'));
    expect(toastMock).not.toHaveBeenCalledWith('내보내기를 완료했습니다', expect.anything());
  });

  it('전체 반려는 판정 경로가 있는 카드마다 반려 판정을 보내고 화면에 남는다', async () => {
    const { verdictCalls } = stubReviewEndpoints([
      queueItem(FIRST, '결제 재시도 정책'),
      queueItem(SECOND, '환불 문서 병합'),
    ]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));

    act(() => result.current.onRejectDialogOpenChange(true));
    act(() => result.current.onRejectAll('근거 문서가 없습니다'));

    // 사유는 전 블록이 공유한다 — 빠진 블록은 판정 경로가 없어 여기서도 빠진다
    await waitFor(() => expect(verdictCalls).toHaveLength(2));
    expect(verdictCalls.every((call) => call.verdict === 'rejected')).toBe(true);
    expect(verdictCalls.every((call) => call.reason === '근거 문서가 없습니다')).toBe(true);

    // 화면 유지 — 다이얼로그만 닫히고 안건이 큐에 남는다. 종결은 최종 내보내기 몫이다
    await waitFor(() => expect(result.current.rejectDialogOpen).toBe(false));
    expect(result.current.selectedId).toBe(FIRST);
    expect(result.current.items).toHaveLength(2);

    // 다시 읽은 상세의 판정으로 카드가 "반려됨"으로 접힌다
    await waitFor(() => expect(result.current.entries.filter((entry) => entry.rejected)).toHaveLength(2));
  });

  it('반려 다이얼로그가 열린 동안은 보던 안건이 목록에서 빠져도 선택 폴백이 보류된다', async () => {
    let hideFirst = false;
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    server.use(
      http.get('*/api/v1/knowledge-review/queue', () => {
        const items = hideFirst
          ? [queueItem(SECOND, '환불 문서 병합')]
          : [queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')];
        return HttpResponse.json({ items, total: items.length, limit: 50, offset: 0 });
      }),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.selectedId).toBe(FIRST));
    act(() => result.current.onRejectDialogOpenChange(true));

    // 열림 중 큐가 다시 와서 보던 행이 빠진다 — 첫 줄로 갈아타면 사유가 다른 안건에 붙는다
    hideFirst = true;
    act(() => result.current.onFiltersChange({ ...result.current.filters, waitingId: 'within-7d' }));

    await waitFor(() => expect(result.current.items).toHaveLength(1));
    expect(result.current.selectedId).toBe(FIRST);

    // 닫으면 정상 폴백이 재개된다
    act(() => result.current.onRejectDialogOpenChange(false));
    await waitFor(() => expect(result.current.selectedId).toBe(SECOND));
  });

  it('카드 반려 제출은 다이얼로그를 연 시점의 안건으로 나간다', async () => {
    const { verdictCalls } = stubReviewEndpoints([
      queueItem(FIRST, '결제 재시도 정책'),
      queueItem(SECOND, '환불 문서 병합'),
    ]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));
    act(() => result.current.onRejectBlock?.(result.current.entries[0]));
    expect(result.current.blockRejectDialogOpen).toBe(true);

    // 열림 중 선택이 다른 안건으로 바뀌어도 제출은 연 시점의 안건으로 나간다
    act(() => result.current.onSelectItem(SECOND));
    act(() => result.current.onRejectBlockSubmit?.('근거 VOC가 한 건뿐입니다'));

    await waitFor(() => expect(verdictCalls).toHaveLength(1));
    expect(verdictCalls[0]).toMatchObject({ proposalId: FIRST, blockIndex: '0', verdict: 'rejected' });
  });

  it('발행 대기 중 다른 안건으로 옮겼으면 완료가 그 선택을 되덮지 않는다', async () => {
    const THIRD = 'prop-third';
    let releasePublish!: () => void;
    const gate = new Promise<void>((resolve) => {
      releasePublish = resolve;
    });
    stubReviewEndpoints([
      queueItem(FIRST, '결제 재시도 정책'),
      queueItem(SECOND, '환불 문서 병합'),
      queueItem(THIRD, '약관 개정 반영'),
    ]);
    server.use(
      http.post('*/api/v1/knowledge-review/queue/:proposalId/publish', async ({ params }) => {
        await gate;
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
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.selectedId).toBe(FIRST));
    act(() => result.current.onPublish());
    act(() => result.current.onSelectItem(THIRD));

    releasePublish();
    await waitFor(() =>
      expect(toastMock).toHaveBeenCalledWith('내보내기를 완료했습니다', expect.objectContaining({ duration: 6000 })),
    );
    expect(result.current.selectedId).toBe(THIRD);

    // 발행 토스트는 전역 액션 버튼 규격만 쓴다 — 토스트별 오버라이드가 되살아나면 안 된다
    const publishToast = toastMock.mock.calls.find(([message]) => message === '내보내기를 완료했습니다');
    expect(publishToast?.[1]).not.toHaveProperty('classNames');
  });

  it('발행 대기 중 선택을 옮겨도 발행된 문서의 발행판 캐시가 무효화된다', async () => {
    let releasePublish!: () => void;
    const gate = new Promise<void>((resolve) => {
      releasePublish = resolve;
    });
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책'), queueItem(SECOND, '환불 문서 병합')]);
    server.use(
      http.post('*/api/v1/knowledge-review/queue/:proposalId/publish', async ({ params }) => {
        await gate;
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
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));
    expect(result.current.selectedId).toBe(FIRST);
    act(() => result.current.onPublish());
    act(() => result.current.onSelectItem(SECOND));

    // 완료 시점의 선택이 아니라 발행을 누른 시점의 문서 키가 무효화된다
    releasePublish();
    await waitFor(() =>
      expect(invalidateSpy.mock.calls.map(([filters]) => filters?.queryKey)).toContainEqual(
        wikiQueries.artifact(`art-${FIRST}`).queryKey,
      ),
    );
  });

  it('발행 요청이 비행 중이면 발행이 잠긴다 — 더블클릭이 두 번 나가지 않는다', async () => {
    let releasePublish!: () => void;
    const gate = new Promise<void>((resolve) => {
      releasePublish = resolve;
    });
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.post('*/api/v1/knowledge-review/queue/:proposalId/publish', async ({ params }) => {
        await gate;
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
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));
    act(() => result.current.onApproveAll());
    await waitFor(() => expect(result.current.publishDisabled).toBe(false));

    act(() => result.current.onPublish());
    await waitFor(() => expect(result.current.publishDisabled).toBe(true));

    releasePublish();
    await waitFor(() => expect(toastMock).toHaveBeenCalledWith('내보내기를 완료했습니다', expect.anything()));
  });

  it('전체 반려가 전량 실패하면 다이얼로그를 닫지 않는다 — 사유가 보존된다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.put('*/api/v1/knowledge-review/queue/:proposalId/blocks/:blockIndex/verdict', () =>
        HttpResponse.json(
          { detail: { code: 'STALE_BLOCK', message: '다른 검토자가 먼저 판정했어요.' } },
          { status: 409 },
        ),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.entries).toHaveLength(3));
    act(() => result.current.onRejectDialogOpenChange(true));
    act(() => result.current.onRejectAll('근거 문서가 없습니다'));

    await waitFor(() =>
      expect(toastMock).toHaveBeenCalledWith('2건을 반려하지 못했습니다. 다른 검토자가 먼저 판정했어요.'),
    );
    // 열린 채 남아야 사유가 보존돼 그대로 다시 보낼 수 있다
    expect(result.current.rejectDialogOpen).toBe(true);
  });

  it('반려할 블록이 없으면 요청 없이 닫고 안내 토스트를 띄운다', async () => {
    const { verdictCalls } = stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
        HttpResponse.json({
          ...detail(String(params.proposalId), false),
          blocks: [],
          block_changes: [{ change: 'removed', block_index: null, base_block_index: 1 }],
        }),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    // 빠진 블록 카드 하나뿐 — 판정 경로가 없어 보낼 대상이 없다
    await waitFor(() => expect(result.current.entries).toHaveLength(1));
    act(() => result.current.onRejectDialogOpenChange(true));
    act(() => result.current.onRejectAll('근거 문서가 없습니다'));

    expect(result.current.rejectDialogOpen).toBe(false);
    expect(toastMock).toHaveBeenCalledWith('반려할 블록이 없습니다');
    expect(verdictCalls).toHaveLength(0);
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

  /** 첫 응답에는 힌트 대상이 없고, 둘째 응답부터 목록에 들어오는 큐 */
  function stubTwoPhaseQueue() {
    let requestCount = 0;
    server.use(
      http.get('*/api/v1/knowledge-review/queue', () => {
        requestCount += 1;
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
      http.get('*/api/v1/auth/me', () =>
        HttpResponse.json({
          user_id: 99,
          name: '검토자',
          email: 'reviewer@catchup.dev',
          role: 'user',
          status: 'active',
        }),
      ),
    );
  }

  it('힌트는 찾을 때까지 재시도한다 — 뒤늦게 목록에 들어온 안건도 골라진다', async () => {
    stubTwoPhaseQueue();
    const { result } = renderHook(() => useReviewQueueModel({ preselectArtifactId: `art-${SECOND}` }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.items).toHaveLength(1));
    expect(result.current.selectedId).toBe(FIRST);

    act(() => result.current.onFiltersChange({ ...result.current.filters, waitingId: 'within-7d' }));

    await waitFor(() => expect(result.current.selectedId).toBe(SECOND));
  });

  it('힌트를 찾기 전에 사용자가 고르면 즉시 포기한다', async () => {
    stubTwoPhaseQueue();
    const { result } = renderHook(() => useReviewQueueModel({ preselectArtifactId: `art-${SECOND}` }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.items).toHaveLength(1));
    act(() => result.current.onSelectItem(FIRST));

    // 나중에 대상이 목록에 들어와도 사용자의 선택을 덮지 않는다
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

  /** ch-1을 내가 관리하는 채널로 돌려주는 응답 */
  const adminChannels = () =>
    HttpResponse.json({
      channels: [
        {
          id: 'ch-1',
          name: '결제',
          workspace_id: 1,
          is_admin: true,
          document_count: 0,
          folders: [],
          purpose_presets: [],
          definitions: [],
        },
      ],
    });

  it('담당자 없는 문서 — 관리자는 지정·해제가 열리지만 담당자가 아니라 목록에는 서지 않는다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(http.get('*/api/v1/wiki/channels', adminChannels));
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.canAssignOwners).toBe(true));
    expect(result.current.canRemoveOwners).toBe(true);
    expect(result.current.ownerNotice).toBe('no-owner');
    // 카드에는 담당자만 선다 — 관리자 역할은 배너가 아니라 담당자 행의 배지로만 드러난다
    expect(result.current.participants).toEqual([]);
  });

  it('담당자이면서 관리자면 내 행에 배지가 둘 선다 — 담당자 + 채널 관리자', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.get('*/api/v1/wiki/channels', adminChannels),
      http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
        HttpResponse.json({
          ...detail(String(params.proposalId), false),
          owners: [{ user_id: 99, display_name: '검토자', profile_image_url: null }],
        }),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.participants).toHaveLength(1));
    expect(result.current.participants[0]).toMatchObject({
      userId: 99,
      isMe: true,
      roles: ['담당자', '채널 관리자'],
    });
    expect(result.current.ownerNotice).toBeNull();
  });

  it('남의 담당자 행에는 관리자 배지를 붙이지 않는다 — 서버가 남의 관리자 여부를 주지 않는다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.get('*/api/v1/wiki/channels', adminChannels),
      http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
        HttpResponse.json({
          ...detail(String(params.proposalId), false),
          owners: [{ user_id: 7, display_name: '팀원F', profile_image_url: null }],
        }),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.participants).toHaveLength(1));
    // 남의 관리자 여부는 서버가 주지 않아 배지가 붙지 않는다
    expect(result.current.participants[0]).toMatchObject({ userId: 7, isMe: false, roles: ['담당자'] });
  });

  it('담당자 없는 문서 — 일반 구성원도 배너는 서고 지정·해제는 닫힌다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.ownerNotice).toBe('no-owner'));
    expect(result.current.participants).toEqual([]);
    expect(result.current.canAssignOwners).toBe(false);
    expect(result.current.canRemoveOwners).toBe(false);
  });

  it('타 담당자가 있는 문서 — 관리자가 아니면 지정·해제가 닫히고 배너만 선다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
        HttpResponse.json({
          ...detail(String(params.proposalId), false),
          owners: [{ user_id: 7, display_name: '팀원F', profile_image_url: null }],
        }),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.participants).toHaveLength(1));
    expect(result.current.participants[0]).toMatchObject({ userId: 7, isMe: false, roles: ['담당자'] });
    expect(result.current.ownerNotice).toBe('other-owner');
    expect(result.current.canAssignOwners).toBe(false);
    expect(result.current.canRemoveOwners).toBe(false);
  });

  it('담당자 본인 — 지정은 열리지만 해제는 닫히고(관리자만) 배너가 없다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
        HttpResponse.json({
          ...detail(String(params.proposalId), false),
          owners: [{ user_id: 99, display_name: '검토자', profile_image_url: null }],
        }),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.canAssignOwners).toBe(true));
    expect(result.current.canRemoveOwners).toBe(false);
    expect(result.current.ownerNotice).toBeNull();
    // 관리자가 아니라 배지는 담당자 하나다
    expect(result.current.participants[0]).toMatchObject({ userId: 99, isMe: true, roles: ['담당자'] });
    // 이미 담당자인 사람은 추가 후보에서 빠진다 — 멤버 목록이 비어 있어 후보도 빈다
    expect(result.current.ownerCandidates).toEqual([]);
  });

  it('담당자 활동 줄 — 그 사람의 가장 최근 판정이 상대시각 검토로 나오고, 이력이 없으면 검토 전이다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    server.use(
      http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
        HttpResponse.json({
          ...detail(String(params.proposalId), false),
          owners: [
            { user_id: 7, display_name: '팀원F', profile_image_url: null },
            { user_id: 8, display_name: '직원10', profile_image_url: null },
          ],
          blocks: [
            {
              ...proposedBlock(0, '재시도 정책'),
              verdict: { ...blockVerdict(FIRST, 0), reviewer: 'user:7', reviewed_at: twoDaysAgo },
            },
            {
              ...proposedBlock(1, 'PG 점검 시간 예외'),
              verdict: { ...blockVerdict(FIRST, 1), reviewer: 'user:7', reviewed_at: threeHoursAgo },
            },
          ],
        }),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.participants).toHaveLength(2));
    // 두 판정 중 최근 것이 이긴다
    expect(result.current.participants[0].description).toBe('3시간 전 검토');
    // 판정 이력이 없는 담당자
    expect(result.current.participants[1].description).toBe('검토 전');
  });

  it('reviewer가 user:{id} 형식이 아니면 매칭 실패로 보고 검토 전으로 남긴다 — 예외를 던지지 않는다', async () => {
    stubReviewEndpoints([queueItem(FIRST, '결제 재시도 정책')]);
    server.use(
      http.get('*/api/v1/knowledge-review/queue/:proposalId', ({ params }) =>
        HttpResponse.json({
          ...detail(String(params.proposalId), false),
          owners: [{ user_id: 7, display_name: '팀원F', profile_image_url: null }],
          blocks: [
            // 이름 문자열 reviewer — 숫자 id를 캘 수 없어 어느 담당자와도 맞지 않는다
            { ...proposedBlock(0, '재시도 정책'), verdict: { ...blockVerdict(FIRST, 0), reviewer: '팀원F' } },
          ],
        }),
      ),
    );
    const { result } = renderHook(() => useReviewQueueModel(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.participants).toHaveLength(1));
    expect(result.current.participants[0].description).toBe('검토 전');
  });
});
