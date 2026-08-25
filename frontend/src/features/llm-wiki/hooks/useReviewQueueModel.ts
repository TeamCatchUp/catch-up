'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { toast } from '@/shared/components/ui/toast';
import { authQueries } from '@/shared/queries/auth.queries';

import { mapReviewProposalDetail } from '../api/knowledgeReviewDetailMappers';
import { mapReviewQueueItem, type ReviewQueueRowData } from '../api/knowledgeReviewMappers';
import { createWikiLocationIndex, mapWikiMembers, resolveDocumentBreadcrumbs } from '../api/wikiMappers';
import type { ReviewParticipant } from '../components/review-queue/ReviewParticipantsCard';
import {
  buildReviewQueueParams,
  filterQueueItems,
  INITIAL_REVIEW_QUEUE_FILTER_STATE,
  resolveClientQueueFilter,
} from '../components/review-queue/reviewQueueFilters';
import type { ReviewQueuePageProps } from '../components/review-queue/ReviewQueuePage';
import {
  type BlockVerdictTarget,
  useReviewBlockVerdictMutation,
  useReviewBulkVerdictMutation,
  useReviewPublishMutation,
} from '../queries/knowledgeReview.mutations';
import { knowledgeReviewQueries } from '../queries/knowledgeReview.queries';
import { wikiQueries } from '../queries/wiki.queries';
import {
  useAssignWikiArtifactOwnersMutation,
  useRemoveWikiArtifactOwnerMutation,
} from '../queries/wikiArtifactOwners.mutations';
import type { BlockDiffEntry } from '../types/llmWikiDiff';
import type { DocumentBreadcrumb } from '../types/llmWikiModel';
import { buildBlockDiff } from '../utils/diff/buildBlockDiff';
import { useQueryErrorToast } from './useQueryErrorToast';

/** 큐는 서버 기본값과 같은 쪽 크기로 한 번만 가져온다 — 목록 패널에 쪽 컨트롤 시안이 없다 */
const QUEUE_PAGE_SIZE = 50;

/** 전역 토스트가 1초라 액션 버튼을 누를 시간이 없다 — 이 토스트만 길게 연다 */
const ACTION_TOAST_DURATION = 6000;

/** 지금 그릴 안건. 고른 안건이 목록에 남아 있으면 지키고, 빠졌으면 첫 줄로 내려온다. */
function resolveSelectedRowId(selectedId: string | null, rows: readonly ReviewQueueRowData[]): string | null {
  if (selectedId === null) return rows[0]?.id ?? null;
  return rows.some((row) => row.id === selectedId) ? selectedId : (rows[0]?.id ?? null);
}

/**
 * 지금 안건이 큐에서 빠진 뒤 갈 자리. 다음 줄, 마지막이면 이전 줄, 혼자였으면 없음이다.
 * 줄이 빠지기 전에 재야 결정적이라 요청을 내는 시점에 부른다.
 */
function resolveNextRowId(rows: readonly ReviewQueueRowData[], currentId: string | null): string | null {
  const index = rows.findIndex((row) => row.id === currentId);
  if (index < 0) return null;
  return rows[index + 1]?.id ?? rows[index - 1]?.id ?? null;
}

/** 판정을 보낼 수 있는 카드. 빠진 블록은 변경안에 자리가 없어 결정을 받지 못한다 */
function hasVerdictPath(
  entry: BlockDiffEntry,
): entry is BlockDiffEntry & { blockIndex: number; blockContentHash: string } {
  return entry.blockIndex !== null && entry.blockContentHash !== null;
}

/** 일괄 판정(전체 승인·반려)이 보낼 카드. 이미 판정된 카드도 덮어쓰기 대상으로 함께 담는다 */
function collectVerdictTargets(entries: readonly BlockDiffEntry[]): BlockVerdictTarget[] {
  return entries
    .filter(hasVerdictPath)
    .map((entry) => ({ blockIndex: entry.blockIndex, block_content_hash: entry.blockContentHash }));
}

/** 서버의 미결정 검사와 같은 집합 — 변경 없는 블록은 카드가 없어 여기 들지 않는다 */
function hasUndecidedBlock(entries: readonly BlockDiffEntry[]): boolean {
  return entries.some((entry) => hasVerdictPath(entry) && !entry.approved && !entry.rejected);
}

/** 카드 반려 다이얼로그가 든 것 — 연 시점의 안건을 함께 물어 제출이 그 안건으로 나간다 */
interface RejectingBlock {
  entry: BlockDiffEntry;
  proposalId: string;
}

interface ReviewQueueModelOptions {
  /** 처음 고를 안건의 힌트. 이 문서의 계류 안건을 찾아 골라 준다 */
  preselectArtifactId?: string | null;
}

/**
 * 검토 큐 화면의 조회 상태·판정 요청을 관리하는 페이지 모델 훅.
 * 반환값이 곧 화면 props다 — 라우트는 받아 넘기기만 한다.
 */
export function useReviewQueueModel({
  preselectArtifactId = null,
}: ReviewQueueModelOptions = {}): ReviewQueuePageProps {
  const router = useRouter();

  const [filters, setFilters] = useState(INITIAL_REVIEW_QUEUE_FILTER_STATE);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [rejecting, setRejecting] = useState<RejectingBlock | null>(null);

  const params = useMemo(
    () => buildReviewQueueParams(filters, { limit: QUEUE_PAGE_SIZE, offset: 0, now: new Date() }),
    [filters],
  );

  const queueQuery = useQuery(knowledgeReviewQueries.queue(params));
  const channelsQuery = useQuery(wikiQueries.channels());
  const membersQuery = useQuery(wikiQueries.members());
  const meQuery = useQuery(authQueries.me());
  const queue = queueQuery.data;
  const channels = channelsQuery.data;
  const members = membersQuery.data;
  const me = meQuery.data;

  // 힌트는 대상을 찾을 때까지 목록이 올 때마다 재시도하고, 사용자가 직접 고르면 즉시 포기한다.
  // 첫 쪽(50행) 밖의 대상은 끝내 찾지 못한다 — 쪽 컨트롤이 없는 화면의 계약이다.
  const [preselectedId, setPreselectedId] = useState<string | null>(null);
  const [preselectResolved, setPreselectResolved] = useState(preselectArtifactId === null);
  if (!preselectResolved) {
    if (selectedId !== null) {
      setPreselectResolved(true);
    } else {
      const hinted = queue?.items.find((item) => item.artifact.id === preselectArtifactId)?.proposal_id;
      if (hinted !== undefined) {
        setPreselectResolved(true);
        setPreselectedId(hinted);
      }
    }
  }

  // 서버가 하나씩만 받는 축의 다중 선택분을 응답 위에서 좁힌다.
  // 좁히기는 받은 첫 쪽(50행) 위라 그 밖의 일치 안건은 목록·건수에서 빠질 수 있다.
  const clientFilter = resolveClientQueueFilter(filters);
  const clientNarrowed = clientFilter.channelIds.length > 0 || clientFilter.ownerUserIds.length > 0;
  const queueItems = useMemo(
    () => filterQueueItems(queue?.items ?? [], resolveClientQueueFilter(filters)),
    [queue?.items, filters],
  );

  const rows = useMemo(() => queueItems.map(mapReviewQueueItem), [queueItems]);
  // 고른 적이 없을 때만 힌트가 자리를 채운다 — 사용자의 선택이 언제나 앞선다
  const pendingSelectedId = selectedId ?? preselectedId;
  // 반려 다이얼로그가 열린 동안은 행이 목록에서 빠져도 폴백을 보류한다 — 사유가 다른 안건에 붙으면 안 된다
  const dialogHold = rejectDialogOpen || rejecting !== null;
  const selectedRowId =
    dialogHold && pendingSelectedId !== null ? pendingSelectedId : resolveSelectedRowId(pendingSelectedId, rows);
  const selectedRow = rows.find((row) => row.id === selectedRowId);
  const selectedItem = queueItems.find((item) => item.proposal_id === selectedRowId);

  const detailQuery = useQuery(knowledgeReviewQueries.queueItem(selectedRowId ?? ''));
  const detailDto = detailQuery.data;
  const detail = useMemo(() => (detailDto ? mapReviewProposalDetail(detailDto) : null), [detailDto]);

  // 이 화면의 조회 실패는 판정 토스트와 같은 전역 자리에 한 번만 뜬다
  useQueryErrorToast(queueQuery.error ?? detailQuery.error ?? channelsQuery.error ?? membersQuery.error);

  // 발행 완료 시점의 화면 선택을 읽는 거울 — 대기 중 사용자가 옮긴 선택을 되덮지 않기 위한 것
  const selectedRowIdRef = useRef<string | null>(null);
  useEffect(() => {
    selectedRowIdRef.current = selectedRowId;
  });

  const verdictMutation = useReviewBlockVerdictMutation();
  const publishMutation = useReviewPublishMutation(selectedRowId ?? '', detail?.artifactId);
  const bulkVerdictMutation = useReviewBulkVerdictMutation();
  const assignOwnersMutation = useAssignWikiArtifactOwnersMutation();
  const removeOwnerMutation = useRemoveWikiArtifactOwnerMutation();

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

  const myUserId = me?.user_id ?? null;
  const owners = detail?.owners ?? [];
  const isMeOwner = myUserId !== null && owners.some((owner) => owner.userId === myUserId);
  // 백엔드 can_manage_owners와 같은 판: 채널 문서는 그 채널 관리자, 미분류 문서는 전역 ADMIN이다
  const isArtifactAdmin = detail
    ? detail.channelId === null
      ? me?.role === 'admin'
      : (channels?.channels.find((channel) => channel.id === detail.channelId)?.is_admin ?? false)
    : false;
  const canAssignOwners = isArtifactAdmin || isMeOwner;
  const canRemoveOwners = isArtifactAdmin;

  // 담당자가 없으면 카드도 빈다 — 판정 폴백은 구성원 전체라 특정인을 행으로 세울 근거가 없다
  const participants: ReviewParticipant[] = owners.map((owner) => ({
    id: String(owner.userId),
    userId: owner.userId,
    name: owner.displayName,
    isMe: owner.userId === myUserId,
    avatarSrc: owner.profileImageUrl,
  }));

  const ownerNotice = detail === null ? null : owners.length === 0 ? 'no-owner' : isMeOwner ? null : 'other-owner';

  const ownerIds = new Set(owners.map((owner) => owner.userId));
  // 후보 행의 직책(B17)·(나) 외 보조 표기는 멤버 응답에 없어 비운다
  const ownerCandidates = (members ? mapWikiMembers(members) : [])
    .filter((member) => !ownerIds.has(member.userId))
    .map((member) => ({
      id: String(member.userId),
      label: member.displayName,
      suffixLabel: member.userId === myUserId ? '(나)' : undefined,
    }));

  const assignOwners = (userIds: readonly number[]) => {
    if (!detail || userIds.length === 0) return;
    assignOwnersMutation.mutate(
      { artifactId: detail.artifactId, userIds },
      { onSuccess: () => toast('담당자를 지정했습니다') },
    );
  };

  const removeOwner = (userId: number) => {
    if (!detail) return;
    removeOwnerMutation.mutate({ artifactId: detail.artifactId, userId });
  };

  const selectItem = (proposalId: string) => setSelectedId(proposalId);

  const approveBlock = (entry: BlockDiffEntry) => {
    // 판정 경로가 없는 카드(발행판에서만 빠진 블록)는 요청 자체가 성립하지 않는다
    if (selectedRowId === null || entry.blockIndex === null || entry.blockContentHash === null) return;
    verdictMutation.mutate({
      proposalId: selectedRowId,
      blockIndex: entry.blockIndex,
      verdict: 'approved',
      block_content_hash: entry.blockContentHash,
    });
  };

  const rejectBlock = (entry: BlockDiffEntry) => {
    if (selectedRowId === null || entry.blockIndex === null || entry.blockContentHash === null) return;
    // 여는 순간의 안건을 고정한다 — 입력 중 목록이 갈려도 제출이 이 안건으로 나간다
    setSelectedId(selectedRowId);
    setRejecting({ entry, proposalId: selectedRowId });
  };

  // 사유는 이미 트림돼 온다 — 빈 사유는 서버가 422로 막는 계약이라 다이얼로그가 먼저 잠근다
  const submitBlockReject = (reason: string) => {
    if (rejecting === null || rejecting.entry.blockIndex === null || rejecting.entry.blockContentHash === null) {
      return;
    }
    verdictMutation.mutate(
      {
        proposalId: rejecting.proposalId,
        blockIndex: rejecting.entry.blockIndex,
        verdict: 'rejected',
        rejection_reason: reason,
        block_content_hash: rejecting.entry.blockContentHash,
      },
      { onSuccess: () => setRejecting(null) },
    );
  };

  /**
   * 전체 승인은 판정 경로가 있는 전 카드를 승인으로 덮는다 — 발행은 별도 클릭으로 남는다.
   * 보낼 카드가 없으면(빠진 블록만) 요청 자체가 성립하지 않는다.
   */
  const approveAll = () => {
    const targets = collectVerdictTargets(entries);
    if (selectedRowId === null || targets.length === 0) return;

    bulkVerdictMutation.mutate(
      { proposalId: selectedRowId, targets, verdict: 'approved' },
      {
        onSuccess: ({ requested, failed, message }) => {
          if (failed === 0) {
            toast(`${requested}건 모두 승인했습니다`);
            return;
          }
          // 성공분은 이미 서버에 남았다 — 다시 읽은 상세가 그만큼을 판정된 카드로 보인다
          toast(`${failed}건을 승인하지 못했습니다. ${message ?? ''}`.trim());
        },
      },
    );
  };

  /**
   * 전체 반려도 전체 승인과 같은 블록 판정 일괄 전송이다 — 사유를 전 블록이 공유한다.
   * 판정만 쌓이고 안건은 큐에 남는다 — 종결은 최종 내보내기 몫이다.
   */
  const rejectAll = (reason: string) => {
    const targets = collectVerdictTargets(entries);
    // 보낼 카드가 없으면(빠진 블록만) 요청 없이 닫는다 — 무음 증발로 읽히지 않게 안내를 남긴다
    if (selectedRowId === null || targets.length === 0) {
      setRejectDialogOpen(false);
      toast('반려할 블록이 없습니다');
      return;
    }

    bulkVerdictMutation.mutate(
      { proposalId: selectedRowId, targets, verdict: 'rejected', rejection_reason: reason },
      {
        onSuccess: ({ requested, failed, message }) => {
          // 전량 실패면 닫지 않는다 — 사유가 남아 그대로 다시 보낼 수 있어야 한다
          if (failed > 0 && failed === requested) {
            toast(`${failed}건을 반려하지 못했습니다. ${message ?? ''}`.trim());
            return;
          }
          setRejectDialogOpen(false);
          if (failed === 0) {
            toast(`${requested}건 모두 반려했습니다`);
            return;
          }
          // 성공분은 이미 서버에 남았다 — 다시 읽은 상세가 그만큼을 판정된 카드로 보인다
          toast(`${failed}건을 반려하지 못했습니다. ${message ?? ''}`.trim());
        },
      },
    );
  };

  const publish = () => {
    if (!detail || selectedRowId === null) return;
    const { artifactId } = detail;
    const publishedRowId = selectedRowId;
    const nextRowId = resolveNextRowId(rows, publishedRowId);
    publishMutation.mutate(
      { base_revision_id: detail.baseRevisionId },
      {
        onSuccess: (result) => {
          // 발행된 안건은 큐에서 빠진다 — 발행한 행을 그대로 보고 있을 때만 다음 안건으로 옮긴다
          if (selectedRowIdRef.current === publishedRowId) setSelectedId(nextRowId);
          // 전 블록 반려 종결은 새 판이 없다 — 열어 볼 발행본이 없어 안내만 남긴다
          if (result.verdict === 'rejected') {
            toast('모든 변경을 반려해 문서를 바꾸지 않고 종결했습니다');
            return;
          }
          toast('내보내기를 완료했습니다', {
            duration: ACTION_TOAST_DURATION,
            action: { label: '열기', onClick: () => router.push(`/llm-wiki/${artifactId}`) },
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
    selectedId: selectedRowId,
    onSelectItem: selectItem,
    breadcrumbs,
    title,
    waitingLabel: selectedRow?.waitingLabel ?? '',
    summary: selectedItem?.summary ?? '',
    participants,
    ownerNotice,
    canAssignOwners,
    canRemoveOwners,
    ownerCandidates,
    onAssignOwners: assignOwners,
    onRemoveOwner: removeOwner,
    entries,
    canReview: detail?.canReview ?? false,
    canReject: detail?.canReview ?? false,
    // 미판정 카드가 남으면 서버가 어차피 거절한다 — 보이는 카드만 세므로 변경 없는 블록에 막히지 않는다
    publishDisabled: detail === null || hasUndecidedBlock(entries),
    channelOptions: (channels?.channels ?? []).map((channel) => ({ id: channel.id, label: channel.name })),
    assigneeOptions: (members ? mapWikiMembers(members) : []).map((member) => ({
      id: String(member.userId),
      label: member.displayName,
    })),
    filters,
    onFiltersChange: setFilters,
    onPreview: preview,
    onApproveBlock: approveBlock,
    onRejectBlock: rejectBlock,
    onPublish: publish,
    onApproveAll: approveAll,
    rejectDialogOpen,
    // 여는 순간의 안건을 고정한다 — 열림 중 목록이 갈려도 사유가 그 안건에 남는다
    onRejectDialogOpenChange: (open: boolean) => {
      if (open && selectedRowId !== null) setSelectedId(selectedRowId);
      setRejectDialogOpen(open);
    },
    onRejectAll: rejectAll,
    rejectPending: bulkVerdictMutation.isPending,
    blockRejectDialogOpen: rejecting !== null,
    onBlockRejectDialogOpenChange: (open: boolean) => {
      if (!open) setRejecting(null);
    },
    onRejectBlockSubmit: submitBlockReject,
    blockRejectPending: verdictMutation.isPending,
  };
}
