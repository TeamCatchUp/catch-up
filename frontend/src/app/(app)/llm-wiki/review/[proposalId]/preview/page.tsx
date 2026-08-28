'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';

import { mapReviewProposalDetail } from '@/features/llm-wiki/api/knowledgeReviewDetailMappers';
import { createWikiLocationIndex, resolveDocumentBreadcrumbs } from '@/features/llm-wiki/api/wikiMappers';
import WikiDocumentPageSkeleton from '@/features/llm-wiki/components/document/states/WikiDocumentPageSkeleton';
import { composeProposalPreview } from '@/features/llm-wiki/components/review-queue/preview/composeProposalPreview';
import ProposalPreviewPage from '@/features/llm-wiki/components/review-queue/preview/ProposalPreviewPage';
import { useQueryErrorToast } from '@/features/llm-wiki/hooks/useQueryErrorToast';
import { knowledgeReviewQueries } from '@/features/llm-wiki/queries/knowledgeReview.queries';
import { wikiQueries } from '@/features/llm-wiki/queries/wiki.queries';
import type { DocumentBreadcrumb } from '@/features/llm-wiki/types/llmWikiModel';
import { formatRelativeTime } from '@/shared/utils/formatDate';

/**
 * 제안본 미리보기. 발행판이 아니라 검토 중인 변경안을 블록 판정 반영본으로 읽는다.
 * 발행된 적 없는 문서도 열린다 — 재료가 검토 큐 상세라 발행판 조회를 타지 않는다.
 */
export default function Page() {
  const router = useRouter();
  const { proposalId } = useParams<{ proposalId: string }>();
  const detailQuery = useQuery(knowledgeReviewQueries.queueItem(proposalId));
  const channelsQuery = useQuery(wikiQueries.channels());

  useQueryErrorToast(detailQuery.error ?? channelsQuery.error);

  const detail = useMemo(
    () => (detailQuery.data ? mapReviewProposalDetail(detailQuery.data) : null),
    [detailQuery.data],
  );
  const items = useMemo(() => (detail ? composeProposalPreview(detail) : []), [detail]);
  const locationIndex = useMemo(
    () => createWikiLocationIndex(channelsQuery.data?.channels ?? []),
    [channelsQuery.data],
  );

  if (detailQuery.isPending) return <WikiDocumentPageSkeleton />;
  // 에러 시각은 문서 화면과 같게 만들지 않는다 — 실패는 토스트로만 알린다
  if (!detail) return null;

  const { channelId, folderId } = detail;
  const title = detail.title ?? '';
  // 제목 없는 문서는 마디를 달지 않는다 — 빈 마디가 경로 끝에 남는다
  const locationBreadcrumbs = resolveDocumentBreadcrumbs(locationIndex, channelId, folderId);
  const breadcrumbs: DocumentBreadcrumb[] = title
    ? [...locationBreadcrumbs, { kind: 'document', label: title }]
    : locationBreadcrumbs;

  return (
    <ProposalPreviewPage
      title={title}
      owners={detail.owners}
      timeLabel={formatRelativeTime(detail.createdAt)}
      breadcrumbs={breadcrumbs}
      items={items}
      onBreadcrumbClick={(crumb) => {
        if (crumb.kind === 'channel' && channelId) router.push(`/llm-wiki/channel/${channelId}`);
        if (crumb.kind === 'folder' && folderId) router.push(`/llm-wiki/folder/${folderId}`);
      }}
    />
  );
}
