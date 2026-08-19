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
  useReviewBlockVerdictMutation,
  useReviewPublishMutation,
} from '@/features/llm-wiki/queries/knowledgeReview.mutations';
import { knowledgeReviewQueries } from '@/features/llm-wiki/queries/knowledgeReview.queries';
import { wikiQueries } from '@/features/llm-wiki/queries/wiki.queries';
import type { BlockDiffEntry } from '@/features/llm-wiki/types/llmWikiDiff';
import type { DocumentBreadcrumb } from '@/features/llm-wiki/types/llmWikiModel';
import { buildBlockDiff } from '@/features/llm-wiki/utils/diff/buildBlockDiff';

/** 큐는 서버 기본값과 같은 쪽 크기로 한 번만 가져온다 — 목록 패널에 쪽 컨트롤 시안이 없다 */
const QUEUE_PAGE_SIZE = 50;

/**
 * 블록 반려는 사유가 필수(없으면 422)인데 사유 입력 시안이 없다.
 * 자리가 생기기 전까지 진입점을 닫아 보낼 수 없는 요청을 막는다.
 */
const CAN_REJECT_BLOCK = false;

export default function Page() {
  const router = useRouter();

  const [filters, setFilters] = useState(INITIAL_REVIEW_QUEUE_FILTER_STATE);
  const [selectedId, setSelectedId] = useState<string | null>(null);

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

  // 미판정 블록이 하나라도 남으면 서버가 발행을 거부한다 — 변경 없는 블록도 판정 대상이다
  const publishDisabled = detail === null || detail.blocks.some((block) => block.verdict === null);

  const approveBlock = (entry: BlockDiffEntry) => {
    // 판정 경로가 없는 카드(발행판에서만 빠진 블록)는 요청 자체가 성립하지 않는다
    if (entry.blockIndex === null || entry.blockContentHash === null) return;
    verdictMutation.mutate({
      blockIndex: entry.blockIndex,
      verdict: 'approved',
      block_content_hash: entry.blockContentHash,
    });
  };

  const publish = () => {
    if (detail) publishMutation.mutate({ base_revision_id: detail.baseRevisionId });
  };

  // 미리보기 대상은 제안본이라 proposalId를 동봉한다 — 열람 전용 제안 뷰는 아직 없어 에디터 라우트가 대신한다
  const preview = () => {
    if (detail) router.push(`/llm-wiki/${detail.artifactId}?proposalId=${detail.proposalId}`);
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
    />
  );
}
