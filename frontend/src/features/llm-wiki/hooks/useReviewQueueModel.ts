'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { buttonVariants } from '@/shared/components/ui/button';
import { toast } from '@/shared/components/ui/toast';

import { mapReviewProposalDetail } from '../api/knowledgeReviewDetailMappers';
import { mapReviewQueueItem, type ReviewQueueRowData } from '../api/knowledgeReviewMappers';
import { createWikiLocationIndex, mapWikiMembers, resolveDocumentBreadcrumbs } from '../api/wikiMappers';
import type { ReviewParticipant } from '../components/review-queue/ReviewParticipantsCard';
import {
  buildReviewQueueParams,
  filterQueueItems,
  INITIAL_REVIEW_QUEUE_FILTER_STATE,
  resolveClientQueueFilter,
  type ReviewQueueFilterState,
} from '../components/review-queue/reviewQueueFilters';
import type { ReviewQueuePageProps } from '../components/review-queue/ReviewQueuePage';
import {
  REVIEW_TOAST_OPTIONS,
  useApproveReviewProposalMutation,
  useRejectReviewProposalMutation,
  useReviewBlockVerdictMutation,
  useReviewPublishMutation,
} from '../queries/knowledgeReview.mutations';
import { knowledgeReviewQueries } from '../queries/knowledgeReview.queries';
import { wikiQueries } from '../queries/wiki.queries';
import type { BlockDiffEntry } from '../types/llmWikiDiff';
import type { DocumentBreadcrumb } from '../types/llmWikiModel';
import { buildBlockDiff } from '../utils/diff/buildBlockDiff';
import { useQueryErrorToast } from './useQueryErrorToast';

/** 큐는 서버 기본값과 같은 쪽 크기로 한 번만 가져온다 — 목록 패널에 쪽 컨트롤 시안이 없다 */
const QUEUE_PAGE_SIZE = 50;

/** 전역 토스트가 1초라 액션 버튼을 누를 시간이 없다 — 이 토스트만 길게 연다 */
const ACTION_TOAST_DURATION = 6000;

/**
 * 통째 판정이 끝난 안건의 상세. 큐에서 줄이 빠져도 판정된 카드로 남겨야 해서 붙잡아 둔다.
 * 서버는 결정된 변경안 상세도 열어 주지만, 승인 뒤에는 발행판과 같아져 변경 목록이 비므로 화면이 든다.
 */
interface DecidedDetailSnapshot {
  proposalId: string;
  entries: readonly BlockDiffEntry[];
  waitingLabel: string;
  summary: string;
}

/**
 * 지금 그릴 안건. 고른 안건이 목록에 남아 있으면 지키고, 빠졌으면 첫 줄로 내려온다.
 * 판정을 붙잡아 둔 안건만은 큐에서 빠져도 지킨다 — 결과를 확인할 자리가 사라지면 안 된다.
 */
function resolveSelectedRowId(
  selectedId: string | null,
  rows: readonly ReviewQueueRowData[],
  decidedId: string | null,
): string | null {
  if (selectedId === null) return rows[0]?.id ?? null;
  if (selectedId === decidedId) return selectedId;
  return rows.some((row) => row.id === selectedId) ? selectedId : (rows[0]?.id ?? null);
}

/**
 * 검토 큐 화면의 조회 상태·판정 요청을 관리하는 페이지 모델 훅.
 * 반환값이 곧 화면 props다 — 라우트는 받아 넘기기만 한다.
 */
export function useReviewQueueModel(): ReviewQueuePageProps {
  const router = useRouter();

  const [filters, setFilters] = useState(INITIAL_REVIEW_QUEUE_FILTER_STATE);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [rejectingEntry, setRejectingEntry] = useState<BlockDiffEntry | null>(null);
  const [decided, setDecided] = useState<DecidedDetailSnapshot | null>(null);

  const params = useMemo(
    () => buildReviewQueueParams(filters, { limit: QUEUE_PAGE_SIZE, offset: 0, now: new Date() }),
    [filters],
  );

  const queueQuery = useQuery(knowledgeReviewQueries.queue(params));
  const channelsQuery = useQuery(wikiQueries.channels());
  const membersQuery = useQuery(wikiQueries.members());
  const queue = queueQuery.data;
  const channels = channelsQuery.data;
  const members = membersQuery.data;

  // 서버가 하나씩만 받는 축의 다중 선택분을 응답 위에서 좁힌다
  const clientFilter = resolveClientQueueFilter(filters);
  const clientNarrowed = clientFilter.channelIds.length > 0 || clientFilter.ownerUserIds.length > 0;
  const queueItems = useMemo(
    () => filterQueueItems(queue?.items ?? [], resolveClientQueueFilter(filters)),
    [queue?.items, filters],
  );

  const rows = useMemo(() => queueItems.map(mapReviewQueueItem), [queueItems]);
  const selectedRowId = resolveSelectedRowId(selectedId, rows, decided?.proposalId ?? null);
  const selectedRow = rows.find((row) => row.id === selectedRowId);
  const selectedItem = queueItems.find((item) => item.proposal_id === selectedRowId);

  const detailQuery = useQuery(knowledgeReviewQueries.queueItem(selectedRowId ?? ''));
  const detailDto = detailQuery.data;
  const detail = useMemo(() => (detailDto ? mapReviewProposalDetail(detailDto) : null), [detailDto]);

  // 이 화면의 조회 실패는 판정 토스트와 같은 자리(우하단)에 한 번만 뜬다
  useQueryErrorToast(
    queueQuery.error ?? detailQuery.error ?? channelsQuery.error ?? membersQuery.error,
    REVIEW_TOAST_OPTIONS,
  );

  const verdictMutation = useReviewBlockVerdictMutation(selectedRowId ?? '');
  const publishMutation = useReviewPublishMutation(selectedRowId ?? '', detail?.artifactId);
  const approveAllMutation = useApproveReviewProposalMutation(selectedRowId ?? '', detail?.artifactId);
  const rejectAllMutation = useRejectReviewProposalMutation(selectedRowId ?? '', detail?.artifactId);

  const entries = useMemo(
    () => (detail ? buildBlockDiff(detail.baseBlocks, detail.blocks, detail.changes, detail.layout) : []),
    [detail],
  );

  const locationIndex = useMemo(() => createWikiLocationIndex(channels?.channels ?? []), [channels]);
  const locationBreadcrumbs = detail
    ? resolveDocumentBreadcrumbs(locationIndex, detail.channelId, detail.folderId)
    : [];

  // 고를 안건이 없으면 문서 마디를 달지 않는다 — 빈 마디가 경로 끝에 남는다
  const title = detail?.title ?? selectedRow?.title ?? '';
  const breadcrumbs: DocumentBreadcrumb[] = title
    ? [...locationBreadcrumbs, { kind: 'document', label: title }]
    : locationBreadcrumbs;

  const participants: ReviewParticipant[] = (detail?.owners ?? []).map((owner) => ({
    id: String(owner.userId),
    name: owner.displayName,
    role: '리뷰어',
    avatarSrc: owner.profileImageUrl,
  }));

  // 큐에서 줄이 빠져도 고른 상세는 그대로 둔다 — 판정 결과를 확인할 자리가 사라지면 안 된다
  const decidedDetail = decided?.proposalId === selectedRowId ? decided : null;
  const displayedEntries = decidedDetail?.entries ?? entries;

  const selectItem = (proposalId: string) => {
    setSelectedId(proposalId);
    setDecided(null);
  };

  // 거르기가 바뀌면 붙잡아 둔 안건을 놓는다 — 고른 안건은 새 목록에 남아 있을 때만 지켜진다
  const changeFilters = (next: ReviewQueueFilterState) => {
    setFilters(next);
    setDecided(null);
  };

  /**
   * 판정이 끝난 직후의 카드 모습을 붙잡는다. 큐에서 줄이 빠져도 이 화면이 남는다.
   * verdict를 주면 전 카드가 그 판정으로 접히고, 주지 않으면 지금 판정 상태(발행 시점)를 그대로 얼린다.
   */
  const freezeDecision = (verdict?: 'approved' | 'rejected') => {
    if (selectedRowId === null) return;
    setSelectedId(selectedRowId);
    setDecided({
      proposalId: selectedRowId,
      entries:
        verdict === undefined
          ? entries
          : entries.map((entry) => ({
              ...entry,
              approved: verdict === 'approved',
              rejected: verdict === 'rejected',
            })),
      waitingLabel: selectedRow?.waitingLabel ?? '',
      summary: selectedItem?.summary ?? '',
    });
  };

  const approveBlock = (entry: BlockDiffEntry) => {
    // 판정 경로가 없는 카드(발행판에서만 빠진 블록)는 요청 자체가 성립하지 않는다
    if (entry.blockIndex === null || entry.blockContentHash === null) return;
    verdictMutation.mutate({
      blockIndex: entry.blockIndex,
      verdict: 'approved',
      block_content_hash: entry.blockContentHash,
    });
  };

  const rejectBlock = (entry: BlockDiffEntry) => {
    if (entry.blockIndex === null || entry.blockContentHash === null) return;
    setRejectingEntry(entry);
  };

  // 사유는 이미 트림돼 온다 — 빈 사유는 서버가 422로 막는 계약이라 다이얼로그가 먼저 잠근다
  const submitBlockReject = (reason: string) => {
    if (rejectingEntry === null || rejectingEntry.blockIndex === null || rejectingEntry.blockContentHash === null) {
      return;
    }
    verdictMutation.mutate(
      {
        blockIndex: rejectingEntry.blockIndex,
        verdict: 'rejected',
        rejection_reason: reason,
        block_content_hash: rejectingEntry.blockContentHash,
      },
      { onSuccess: () => setRejectingEntry(null) },
    );
  };

  const approveAll = () => {
    approveAllMutation.mutate(undefined, {
      onSuccess: () => {
        freezeDecision('approved');
        toast(`${entries.length}건 모두 승인했습니다`, REVIEW_TOAST_OPTIONS);
      },
    });
  };

  const rejectAll = (reason: string) => {
    rejectAllMutation.mutate(
      { reason },
      {
        onSuccess: () => {
          setRejectDialogOpen(false);
          freezeDecision('rejected');
          toast(`${entries.length}건 모두 반려했습니다`, REVIEW_TOAST_OPTIONS);
        },
      },
    );
  };

  const publish = () => {
    if (!detail) return;
    const { artifactId } = detail;
    publishMutation.mutate(
      { base_revision_id: detail.baseRevisionId },
      {
        onSuccess: () => {
          // 발행 시점엔 전 블록에 판정이 있다 — 지금 카드 모습을 그대로 얼려 판정 화면을 지킨다
          freezeDecision();
          toast('내보내기를 완료했습니다', {
            ...REVIEW_TOAST_OPTIONS,
            duration: ACTION_TOAST_DURATION,
            action: { label: '열기', onClick: () => router.push(`/llm-wiki/${artifactId}`) },
            classNames: { actionButton: buttonVariants({ variant: 'capsule-outline-mono', size: 'md' }) },
          });
        },
      },
    );
  };

  // 판정을 반영한 제안본을 연다 — 검토 중 화면을 잃지 않도록 새 탭이다
  const preview = () => {
    if (detail) window.open(`/llm-wiki/review/${detail.proposalId}/preview`, '_blank', 'noopener');
  };

  return {
    items: rows,
    totalCount: clientNarrowed ? rows.length : (queue?.total ?? 0),
    listPending: queueQuery.isPending,
    detailPending: selectedRowId !== null && detailQuery.isPending,
    // 판정을 붙잡아 둔 동안에는 목록이 비어도 상세를 빈 안내로 덮지 않는다
    detailRetained: decidedDetail !== null,
    selectedId: selectedRowId,
    onSelectItem: selectItem,
    breadcrumbs,
    locationBreadcrumbs,
    title,
    waitingLabel: decidedDetail?.waitingLabel ?? selectedRow?.waitingLabel ?? '',
    summary: decidedDetail?.summary ?? selectedItem?.summary ?? '',
    participants,
    entries: displayedEntries,
    // 결정이 끝난 안건에는 남은 판정이 없다 — 권한 없음과 같은 모습으로 진입점을 거둔다
    canReview: decidedDetail === null && (detail?.canReview ?? false),
    canReject: detail?.canReview ?? false,
    // 변경 없는 블록은 판정할 카드가 없어 미판정으로 잠그면 발행이 영영 막힌다.
    // 열어 두고, 서버가 미판정을 거부하면 그 메시지를 토스트로 보인다(사용자 확정).
    publishDisabled: detail === null || decidedDetail !== null,
    channelOptions: (channels?.channels ?? []).map((channel) => ({ id: channel.id, label: channel.name })),
    assigneeOptions: (members ? mapWikiMembers(members) : []).map((member) => ({
      id: String(member.userId),
      label: member.displayName,
    })),
    filters,
    onFiltersChange: changeFilters,
    onPreview: preview,
    onApproveBlock: approveBlock,
    onRejectBlock: rejectBlock,
    onPublish: publish,
    onApproveAll: approveAll,
    rejectDialogOpen,
    onRejectDialogOpenChange: setRejectDialogOpen,
    onRejectAll: rejectAll,
    rejectPending: rejectAllMutation.isPending,
    blockRejectDialogOpen: rejectingEntry !== null,
    onBlockRejectDialogOpenChange: (open: boolean) => {
      if (!open) setRejectingEntry(null);
    },
    onRejectBlockSubmit: submitBlockReject,
    blockRejectPending: verdictMutation.isPending,
  };
}
