'use client';

import { useRouter } from 'next/navigation';

import WikiDashboardPage from '@/features/llm-wiki/components/dashboard/WikiDashboardPage';
import { useWikiDashboardModel } from '@/features/llm-wiki/hooks/useWikiDashboardModel';

const PAGE_SIZE = 20;

/** LLM Wiki 대시보드. 조회 상태와 목록·지표 요청은 페이지 모델 훅이 갖고 화면은 받아 그린다. */
export default function Page() {
  const router = useRouter();
  const model = useWikiDashboardModel(PAGE_SIZE);

  return (
    <WikiDashboardPage
      {...model}
      pageSize={PAGE_SIZE}
      onDocumentClick={(documentId) => router.push(`/llm-wiki/${documentId}`)}
    />
  );
}
