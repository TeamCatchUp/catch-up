'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { mapReviewProposalDetail } from '@/features/llm-wiki/api/knowledgeReviewDetailMappers';
import { mapReviewQueueItem } from '@/features/llm-wiki/api/knowledgeReviewMappers';
import {
  createWikiLocationIndex,
  mapWikiMembers,
  resolveDocumentBreadcrumbs,
} from '@/features/llm-wiki/api/wikiMappers';
import type { ReviewParticipant } from '@/features/llm-wiki/components/review-queue/ReviewParticipantsCard';
import {
  buildReviewQueueParams,
  filterQueueItems,
  INITIAL_REVIEW_QUEUE_FILTER_STATE,
  resolveClientQueueFilter,
} from '@/features/llm-wiki/components/review-queue/reviewQueueFilters';
import ReviewQueuePage from '@/features/llm-wiki/components/review-queue/ReviewQueuePage';
import {
  REVIEW_TOAST_OPTIONS,
  useApproveReviewProposalMutation,
  useRejectReviewProposalMutation,
  useReviewBlockVerdictMutation,
  useReviewPublishMutation,
} from '@/features/llm-wiki/queries/knowledgeReview.mutations';
import { knowledgeReviewQueries } from '@/features/llm-wiki/queries/knowledgeReview.queries';
import { wikiQueries } from '@/features/llm-wiki/queries/wiki.queries';
import type { BlockDiffEntry } from '@/features/llm-wiki/types/llmWikiDiff';
import type { DocumentBreadcrumb } from '@/features/llm-wiki/types/llmWikiModel';
import { buildBlockDiff } from '@/features/llm-wiki/utils/diff/buildBlockDiff';
import { buttonVariants } from '@/shared/components/ui/button';
import { toast } from '@/shared/components/ui/toast';

/** 큐는 서버 기본값과 같은 쪽 크기로 한 번만 가져온다 — 목록 패널에 쪽 컨트롤 시안이 없다 */
const QUEUE_PAGE_SIZE = 50;

/**
 * 블록 반려는 사유가 필수(없으면 422)인데 사유 입력 시안이 없다.
 * 자리가 생기기 전까지 진입점을 닫아 보낼 수 없는 요청을 막는다.
 */
const CAN_REJECT_BLOCK = false;

/** 전역 토스트가 1초라 액션 버튼을 누를 시간이 없다 — 이 토스트만 길게 연다 */
const ACTION_TOAST_DURATION = 6000;

export default function Page() {
  const router = useRouter();

  const [filters, setFilters] = useState(INITIAL_REVIEW_QUEUE_FILTER_STATE);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);

  const params = useMemo(
    () => buildReviewQueueParams(filters, { limit: QUEUE_PAGE_SIZE, offset: 0, now: new Date() }),
    [filters],
  );

  const { data: queue } = useQuery(knowledgeReviewQueries.queue(params));
  const { data: channels } = useQuery(wikiQueries.channels());
  const { data: members } = useQuery(wikiQueries.members());

  // 서버가 하나씩만 받는 축의 다중 선택분을 응답 위에서 좁힌다
  const clientFilter = resolveClientQueueFilter(filters);
  const clientNarrowed = clientFilter.channelIds.length > 0 || clientFilter.ownerUserIds.length > 0;
  const queueItems = useMemo(
    () => filterQueueItems(queue?.items ?? [], resolveClientQueueFilter(filters)),
    [queue?.items, filters],
  );

  const rows = useMemo(() => queueItems.map(mapReviewQueueItem), [queueItems]);
  const selectedRowId = selectedId ?? rows[0]?.id ?? null;
  const selectedRow = rows.find((row) => row.id === selectedRowId);
  const selectedItem = queueItems.find((item) => item.proposal_id === selectedRowId);

  const { data: detailDto } = useQuery(knowledgeReviewQueries.queueItem(selectedRowId ?? ''));
  const detail = useMemo(() => (detailDto ? mapReviewProposalDetail(detailDto) : null), [detailDto]);

  const verdictMutation = useReviewBlockVerdictMutation(selectedRowId ?? '');
  const publishMutation = useReviewPublishMutation(selectedRowId ?? '');
  const approveAllMutation = useApproveReviewProposalMutation(selectedRowId ?? '');
  const rejectAllMutation = useRejectReviewProposalMutation(selectedRowId ?? '');

  const entries = useMemo(
    () => (detail ? buildBlockDiff(detail.baseBlocks, detail.blocks, detail.changes) : []),
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

  // 변경 없는 블록은 판정할 카드가 없어 미판정으로 잠그면 발행이 영영 막힌다.
  // 열어 두고, 서버가 미판정을 거부하면 그 메시지를 토스트로 보인다(사용자 확정).
  const publishDisabled = detail === null;

  const approveBlock = (entry: BlockDiffEntry) => {
    // 판정 경로가 없는 카드(발행판에서만 빠진 블록)는 요청 자체가 성립하지 않는다
    if (entry.blockIndex === null || entry.blockContentHash === null) return;
    verdictMutation.mutate({
      blockIndex: entry.blockIndex,
      verdict: 'approved',
      block_content_hash: entry.blockContentHash,
    });
  };

  const approveAll = () => {
    approveAllMutation.mutate(undefined, {
      onSuccess: () => toast(`${entries.length}건 모두 승인했습니다`, REVIEW_TOAST_OPTIONS),
    });
  };

  const rejectAll = (reason: string) => {
    rejectAllMutation.mutate(
      { reason },
      {
        onSuccess: () => {
          setRejectDialogOpen(false);
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
        onSuccess: () =>
          toast('내보내기를 완료했습니다', {
            ...REVIEW_TOAST_OPTIONS,
            duration: ACTION_TOAST_DURATION,
            action: { label: '열기', onClick: () => router.push(`/llm-wiki/${artifactId}`) },
            classNames: { actionButton: buttonVariants({ variant: 'capsule-outline-mono', size: 'md' }) },
          }),
      },
    );
  };

  // 발행본만 연다 — 검토 중 화면을 잃지 않도록 새 탭이고, 에디터 라우트로는 보내지 않는다
  const preview = () => {
    if (detail) window.open(`/llm-wiki/${detail.artifactId}`, '_blank', 'noopener');
  };

  return (
    <ReviewQueuePage
      items={rows}
      totalCount={clientNarrowed ? rows.length : (queue?.total ?? 0)}
      selectedId={selectedRowId}
      onSelectItem={setSelectedId}
      breadcrumbs={breadcrumbs}
      locationBreadcrumbs={locationBreadcrumbs}
      title={title}
      waitingLabel={selectedRow?.waitingLabel ?? ''}
      summary={selectedItem?.summary ?? ''}
      participants={participants}
      entries={entries}
      canReview={detail?.canReview ?? false}
      canReject={CAN_REJECT_BLOCK}
      publishDisabled={publishDisabled}
      channelOptions={(channels?.channels ?? []).map((channel) => ({ id: channel.id, label: channel.name }))}
      assigneeOptions={(members ? mapWikiMembers(members) : []).map((member) => ({
        id: String(member.userId),
        label: member.displayName,
      }))}
      filters={filters}
      onFiltersChange={setFilters}
      onPreview={preview}
      onApproveBlock={approveBlock}
      onPublish={publish}
      onApproveAll={approveAll}
      rejectDialogOpen={rejectDialogOpen}
      onRejectDialogOpenChange={setRejectDialogOpen}
      onRejectAll={rejectAll}
      rejectPending={rejectAllMutation.isPending}
    />
  );
}
