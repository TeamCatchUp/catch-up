'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { notFound, useParams, useRouter } from 'next/navigation';

import { mapWikiChannelList } from '@/features/llm-wiki/api/wikiMappers';
import type { FolderDocumentRowItem } from '@/features/llm-wiki/components/document/FolderDocumentRow';
import WikiChannelPage from '@/features/llm-wiki/components/space/WikiChannelPage';
import { wikiQueries } from '@/features/llm-wiki/queries/wiki.queries';

const PAGE_SIZE = 20;

/**
 * 채널 화면. 폴더는 채널 목록 응답에 전량 실려 와서 쪽 나눔이 클라이언트 몫이다.
 * 담당자·상태·최근 활동은 폴더에 대응 필드가 없어 비운다.
 */
export default function Page() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [currentPage, setCurrentPage] = useState(1);
  const { data, isPending } = useQuery(wikiQueries.channels());

  // 로딩·에러 시안이 없어 화면을 만들지 않는다
  if (isPending || !data) return null;

  const channel = mapWikiChannelList(data).find((item) => item.id === id);
  if (!channel) notFound();

  const totalPages = Math.max(1, Math.ceil(channel.folders.length / PAGE_SIZE));
  const folderRows: FolderDocumentRowItem[] = channel.folders
    .slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
    .map((folder) => ({ id: folder.id, name: folder.name, owners: [], status: '', lastActivityLabel: '' }));

  return (
    <WikiChannelPage
      channel={channel}
      folderRows={folderRows}
      pageSize={PAGE_SIZE}
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={setCurrentPage}
      onFolderClick={(folderId) => router.push(`/llm-wiki/folder/${folderId}`)}
    />
  );
}
