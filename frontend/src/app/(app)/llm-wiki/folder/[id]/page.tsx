'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { notFound, useParams, useRouter } from 'next/navigation';

import { mapWikiArtifactRows, mapWikiChannelList } from '@/features/llm-wiki/api/wikiMappers';
import type { FolderDocumentRowItem } from '@/features/llm-wiki/components/document/FolderDocumentRow';
import WikiFolderPage from '@/features/llm-wiki/components/space/WikiFolderPage';
import { wikiQueries } from '@/features/llm-wiki/queries/wiki.queries';

const PAGE_SIZE = 20;

/**
 * 폴더 화면. 문서 목록은 limit/offset 쪽 나눔이라 total로 쪽 수를 센다.
 * 폴더 자체의 작성자에 대응하는 필드가 없어 제목 블록의 작성자 줄은 서지 않는다.
 */
export default function Page() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [currentPage, setCurrentPage] = useState(1);

  const channelsQuery = useQuery(wikiQueries.channels());
  const documentsQuery = useQuery(
    wikiQueries.artifacts({ folder_id: id, limit: PAGE_SIZE, offset: (currentPage - 1) * PAGE_SIZE }),
  );

  // 로딩·에러 시안이 없어 화면을 만들지 않는다
  if (channelsQuery.isPending || !channelsQuery.data) return null;

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
  const totalPages = Math.max(1, Math.ceil((documentsQuery.data?.total ?? 0) / PAGE_SIZE));

  return (
    <WikiFolderPage
      channel={channel}
      folder={folder}
      documentRows={documentRows}
      pageSize={PAGE_SIZE}
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={setCurrentPage}
      onDocumentClick={(documentId) => router.push(`/llm-wiki/${documentId}`)}
      onBreadcrumbClick={(_, index) => {
        if (index === 0) router.push(`/llm-wiki/channel/${channel.id}`);
      }}
    />
  );
}
