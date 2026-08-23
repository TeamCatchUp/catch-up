'use client';

import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { notFound, useParams, useRouter } from 'next/navigation';

import { mapWikiArtifactRows, mapWikiChannelList } from '@/features/llm-wiki/api/wikiMappers';
import type { FolderDocumentRowItem } from '@/features/llm-wiki/components/document/FolderDocumentRow';
import WikiSpacePageSkeleton from '@/features/llm-wiki/components/space/states/WikiSpacePageSkeleton';
import WikiFolderPage from '@/features/llm-wiki/components/space/WikiFolderPage';
import { useQueryErrorToast } from '@/features/llm-wiki/hooks/useQueryErrorToast';
import { wikiQueries } from '@/features/llm-wiki/queries/wiki.queries';

const DEFAULT_PAGE_SIZE = 20;

/**
 * 폴더 화면. 문서 목록은 limit/offset 쪽 나눔이라 total로 쪽 수를 센다.
 * 작성자 줄은 폴더를 만든 사람이고, 그 사람이 없는 폴더는 줄 자체가 서지 않는다.
 */
export default function Page() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [currentPage, setCurrentPage] = useState(1);
  const [appliedPageSize, setAppliedPageSize] = useState(pageSize);

  const channelsQuery = useQuery(wikiQueries.channels());
  // placeholderData로 이전 쪽을 유지한다 — 쪽을 넘기는 동안 빈 상태가 끼어들지 않는다
  const documentsQuery = useQuery({
    ...wikiQueries.artifacts({ folder_id: id, limit: pageSize, offset: (currentPage - 1) * pageSize }),
    placeholderData: keepPreviousData,
  });

  useQueryErrorToast(channelsQuery.error ?? documentsQuery.error);

  // 쪽 크기가 바뀌면 offset 기준이 달라진다 — 어긋난 쪽으로 요청이 나가기 전에 1쪽으로 되돌린다.
  if (appliedPageSize !== pageSize) {
    setAppliedPageSize(pageSize);
    setCurrentPage(1);
  }

  if (channelsQuery.isPending) return <WikiSpacePageSkeleton />;
  // 에러 시안이 없어 화면을 만들지 않는다 — 실패는 토스트로만 알린다
  if (!channelsQuery.data) return null;

  const channel = mapWikiChannelList(channelsQuery.data).find((item) =>
    item.folders.some((folder) => folder.id === id),
  );
  const folder = channel?.folders.find((item) => item.id === id);
  if (!channel || !folder) notFound();

  const documentRows: FolderDocumentRowItem[] = mapWikiArtifactRows(documentsQuery.data?.items ?? []).map((row) => ({
    id: row.id,
    name: row.title,
    owners: row.owners,
    status: row.status,
    lastActivityLabel: row.lastActivityLabel,
  }));
  const totalPages = Math.max(1, Math.ceil((documentsQuery.data?.total ?? 0) / pageSize));

  return (
    <WikiFolderPage
      channel={channel}
      folder={folder}
      documentRows={documentRows}
      documentsLoading={documentsQuery.isPending}
      authorName={folder.createdBy?.displayName}
      authorProfileImageUrl={folder.createdBy?.profileImageUrl}
      pageSize={pageSize}
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={setCurrentPage}
      onPageSizeChange={setPageSize}
      onDocumentClick={(documentId) => router.push(`/llm-wiki/${documentId}`)}
      onBreadcrumbClick={(_, index) => {
        if (index === 0) router.push(`/llm-wiki/channel/${channel.id}`);
      }}
    />
  );
}
