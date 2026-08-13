'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import WikiDashboardPage from '@/features/llm-wiki/components/dashboard/WikiDashboardPage';
import { DOCUMENT_ROW_FIXTURES, REVIEW_STAT_CARD_FIXTURES } from '@/features/llm-wiki/fixtures/llmWikiFixtures';

const PAGE_SIZE = 20;

/**
 * LLM Wiki 대시보드. 목록·집계 API가 없어 픽스처를 렌더한다 —
 * 실 API 도착 시 이 픽스처 자리만 교체한다.
 */
export default function Page() {
  const router = useRouter();
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(DOCUMENT_ROW_FIXTURES.length / PAGE_SIZE));

  return (
    <WikiDashboardPage
      stats={REVIEW_STAT_CARD_FIXTURES}
      documents={DOCUMENT_ROW_FIXTURES}
      sortLabel="최근 변경 순"
      pageSize={PAGE_SIZE}
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={setCurrentPage}
      onDocumentClick={(documentId) => router.push(`/llm-wiki/${documentId}`)}
    />
  );
}
