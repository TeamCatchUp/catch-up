'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { buttonVariants } from '@/shared/components/ui/button';
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
  type BlockApproveTarget,
  REVIEW_TOAST_OPTIONS,
  useRejectReviewProposalMutation,
  useReviewBlockVerdictMutation,
  useReviewBulkApproveMutation,
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

/** 일괄 승인이 보낼 카드. 판정 경로가 없는 카드(빠진 블록)와 이미 판정된 카드는 빠진다 */
function collectApproveTargets(entries: readonly BlockDiffEntry[]): BlockApproveTarget[] {
  return entries.flatMap((entry) =>
    entry.blockIndex === null || entry.blockContentHash === null || entry.approved || entry.rejected
      ? []
      : [{ blockIndex: entry.blockIndex, block_content_hash: entry.blockContentHash }],
  );
}

interface ReviewQueueModelOptions {
  /** 처음 고를 안건의 힌트. 이 문서의 계류 안건을 한 번만 골라 준다 */
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
  const [rejectingEntry, setRejectingEntry] = useState<BlockDiffEntry | null>(null);

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

  // 힌트는 목록이 처음 온 순간 한 번만 푼다 — 뒤이은 refetch에 다시 풀리면 선택이 되살아난다
  const [preselectedId, setPreselectedId] = useState<string | null>(null);
  const [preselectResolved, setPreselectResolved] = useState(preselectArtifactId === null);
  if (!preselectResolved && queue !== undefined) {
    setPreselectResolved(true);
    // 이미 처리돼 큐에서 빠진 안건이면 null로 남는다 — 기본 선택이 그대로 선다
    setPreselectedId(queue.items.find((item) => item.artifact.id === preselectArtifactId)?.proposal_id ?? null);
  }

  // 서버가 하나씩만 받는 축의 다중 선택분을 응답 위에서 좁힌다
  const clientFilter = resolveClientQueueFilter(filters);
  const clientNarrowed = clientFilter.channelIds.length > 0 || clientFilter.ownerUserIds.length > 0;
  const queueItems = useMemo(
    () => filterQueueItems(queue?.items ?? [], resolveClientQueueFilter(filters)),
    [queue?.items, filters],
  );

  const rows = useMemo(() => queueItems.map(mapReviewQueueItem), [queueItems]);
  // 고른 적이 없을 때만 힌트가 자리를 채운다 — 사용자의 선택이 언제나 앞선다
  const selectedRowId = resolveSelectedRowId(selectedId ?? preselectedId, rows);
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
  const bulkApproveMutation = useReviewBulkApproveMutation(selectedRowId ?? '');
  const rejectAllMutation = useRejectReviewProposalMutation(selectedRowId ?? '', detail?.artifactId);
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

  const participants: ReviewParticipant[] = owners.map((owner) => ({
    id: String(owner.userId),
    userId: owner.userId,
    name: owner.displayName,
    isMe: owner.userId === myUserId,
    role: '담당자',
    avatarSrc: owner.profileImageUrl,
  }));
  // 담당자가 없으면 검수 폴백인 채널 관리자(나)가 행으로 선다 — 시안 18814:134579
  if (detail !== null && participants.length === 0 && isArtifactAdmin && me && myUserId !== null) {
    participants.push({
      id: String(myUserId),
      userId: myUserId,
      name: me.name,
      isMe: true,
      role: '채널 관리자',
      avatarSrc: me.picture ?? null,
    });
  }

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
      { onSuccess: () => toast('담당자를 지정했습니다', REVIEW_TOAST_OPTIONS) },
    );
  };

  const removeOwner = (userId: number) => {
    if (!detail) return;
    removeOwnerMutation.mutate({ artifactId: detail.artifactId, userId });
  };

  const selectItem = (proposalId: string) => setSelectedId(proposalId);

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

  /**
   * 전체 승인은 미판정 카드에 블록 판정을 일괄로 보낸다 — 발행은 별도 클릭으로 남는다.
   * 보낼 카드가 없으면(전부 판정됨·빠진 블록만) 요청 자체가 성립하지 않는다.
   */
  const approveAll = () => {
    const targets = collectApproveTargets(entries);
    if (targets.length === 0) return;

    bulkApproveMutation.mutate(targets, {
      onSuccess: ({ requested, failed, message }) => {
        if (failed === 0) {
          toast(`${requested}건 모두 승인했습니다`, REVIEW_TOAST_OPTIONS);
          return;
        }
        // 성공분은 이미 서버에 남았다 — 다시 읽은 상세가 그만큼을 판정된 카드로 보인다
        toast(`${failed}건을 승인하지 못했습니다. ${message ?? ''}`.trim(), REVIEW_TOAST_OPTIONS);
      },
    });
  };

  const rejectAll = (reason: string) => {
    const nextRowId = resolveNextRowId(rows, selectedRowId);
    rejectAllMutation.mutate(
      { reason },
      {
        onSuccess: () => {
          setRejectDialogOpen(false);
          // 기각된 안건은 큐에서 빠진다 — 다음 안건으로 옮겨 검토 흐름을 잇는다
          setSelectedId(nextRowId);
          toast(`${entries.length}건 모두 반려했습니다`, REVIEW_TOAST_OPTIONS);
        },
      },
    );
  };

  const publish = () => {
    if (!detail) return;
    const { artifactId } = detail;
    const nextRowId = resolveNextRowId(rows, selectedRowId);
    publishMutation.mutate(
      { base_revision_id: detail.baseRevisionId },
      {
        onSuccess: () => {
          // 발행된 안건도 큐에서 빠진다 — 남은 안건이 없으면 빈 안내가 선다
          setSelectedId(nextRowId);
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
    // 변경 없는 블록은 판정할 카드가 없어 미판정으로 잠그면 발행이 영영 막힌다.
    // 열어 두고, 서버가 미판정을 거부하면 그 메시지를 토스트로 보인다(사용자 확정).
    publishDisabled: detail === null,
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
