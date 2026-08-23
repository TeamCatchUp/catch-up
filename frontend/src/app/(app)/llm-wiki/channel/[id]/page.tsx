'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { notFound, useParams, useRouter } from 'next/navigation';

import { mapWikiChannelList } from '@/features/llm-wiki/api/wikiMappers';
import type { FolderDocumentRowItem } from '@/features/llm-wiki/components/document/FolderDocumentRow';
import WikiSpacePageSkeleton from '@/features/llm-wiki/components/space/states/WikiSpacePageSkeleton';
import WikiChannelPage from '@/features/llm-wiki/components/space/WikiChannelPage';
import { useQueryErrorToast } from '@/features/llm-wiki/hooks/useQueryErrorToast';
import { wikiQueries } from '@/features/llm-wiki/queries/wiki.queries';
import { formatRelativeTime } from '@/shared/utils/formatDate';

const DEFAULT_PAGE_SIZE = 20;

/**
 * 채널 화면. 폴더는 채널 목록 응답에 전량 실려 와서 쪽 나눔이 클라이언트 몫이다.
 * 담당자·상태는 폴더에 대응 필드가 없어 비운다 — 폴더의 created_by는 담당자가 아니다.
 */
export default function Page() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [currentPage, setCurrentPage] = useState(1);
  const [appliedPageSize, setAppliedPageSize] = useState(pageSize);
  const { data, isPending, error } = useQuery(wikiQueries.channels());

  useQueryErrorToast(error);

  // 쪽 크기가 바뀌면 잘라 낼 구간이 달라진다 — 어긋난 구간을 그리기 전에 1쪽으로 되돌린다.
  if (appliedPageSize !== pageSize) {
    setAppliedPageSize(pageSize);
    setCurrentPage(1);
  }

  if (isPending) return <WikiSpacePageSkeleton />;
  // 에러 시안이 없어 화면을 만들지 않는다 — 실패는 토스트로만 알린다
  if (!data) return null;

  const channel = mapWikiChannelList(data).find((item) => item.id === id);
  if (!channel) notFound();

  const totalPages = Math.max(1, Math.ceil(channel.folders.length / pageSize));
  const folderRows: FolderDocumentRowItem[] = channel.folders
    .slice((currentPage - 1) * pageSize, currentPage * pageSize)
    .map((folder) => ({
      id: folder.id,
      name: folder.name,
      owners: [],
      status: '',
      // 활동 시각이 없거나 키가 아예 없으면 칸을 비운다 — 없는 시각을 읽으면 "NaN일 전"이 나간다
      lastActivityLabel: folder.lastActivityAt == null ? '' : formatRelativeTime(folder.lastActivityAt),
    }));

  return (
    <WikiChannelPage
      channel={channel}
      folderRows={folderRows}
      pageSize={pageSize}
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={setCurrentPage}
      onPageSizeChange={setPageSize}
      onFolderClick={(folderId) => router.push(`/llm-wiki/folder/${folderId}`)}
    />
  );
}
