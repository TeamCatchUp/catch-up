'use client';

import { useState } from 'react';
import { notFound, useParams, useRouter } from 'next/navigation';

import WikiChannelPage from '@/features/llm-wiki/components/space/WikiChannelPage';
import { CHANNEL_FOLDER_ROW_FIXTURES, WIKI_CHANNEL_FIXTURE } from '@/features/llm-wiki/fixtures/llmWikiSpaceFixtures';

const PAGE_SIZE = 20;

/**
 * 채널 화면. 채널 내 목록 API가 없어 픽스처 채널을 렌더한다 —
 * 실 API 도착 시 이 픽스처 자리만 교체한다.
 */
export default function Page() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [currentPage, setCurrentPage] = useState(1);

  if (id !== WIKI_CHANNEL_FIXTURE.id) notFound();

  const totalPages = Math.max(1, Math.ceil(CHANNEL_FOLDER_ROW_FIXTURES.length / PAGE_SIZE));

  return (
    <WikiChannelPage
      channel={WIKI_CHANNEL_FIXTURE}
      folderRows={CHANNEL_FOLDER_ROW_FIXTURES}
      authorName="팀원G"
      pageSize={PAGE_SIZE}
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={setCurrentPage}
      onFolderClick={(folderId) => router.push(`/llm-wiki/folder/${folderId}`)}
    />
  );
}
