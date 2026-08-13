'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import WikiFolderPage from '@/features/llm-wiki/components/space/WikiFolderPage';
import {
  FOLDER_DOCUMENT_ROW_FIXTURES,
  WIKI_CHANNEL_FIXTURE,
  WIKI_FOLDER_FIXTURE,
} from '@/features/llm-wiki/fixtures/llmWikiSpaceFixtures';

const PAGE_SIZE = 20;

/**
 * 폴더 화면. 폴더 내 문서 목록 API가 없어 픽스처를 렌더한다 —
 * 실 API 도착 시 이 픽스처 자리만 교체한다(id 조회 포함).
 */
export default function Page() {
  const router = useRouter();
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(FOLDER_DOCUMENT_ROW_FIXTURES.length / PAGE_SIZE));

  return (
    <WikiFolderPage
      channel={WIKI_CHANNEL_FIXTURE}
      folder={WIKI_FOLDER_FIXTURE}
      documentRows={FOLDER_DOCUMENT_ROW_FIXTURES}
      authorName="팀원G"
      pageSize={PAGE_SIZE}
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={setCurrentPage}
      onDocumentClick={(documentId) => router.push(`/llm-wiki/${documentId}`)}
      onBreadcrumbClick={(_, index) => {
        if (index === 0) router.push(`/llm-wiki/channel/${WIKI_CHANNEL_FIXTURE.id}`);
      }}
    />
  );
}
