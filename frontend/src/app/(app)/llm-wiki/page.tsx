'use client';

import { useRouter } from 'next/navigation';

import WikiDashboardPage from '@/features/llm-wiki/components/dashboard/WikiDashboardPage';
import {
  DOCUMENT_ROW_FIXTURES,
  REVIEW_QUEUE_ASSIGNEE_OPTIONS,
  REVIEW_STAT_CARD_FIXTURES,
} from '@/features/llm-wiki/fixtures/llmWikiFixtures';

const PAGE_SIZE = 20;

/** 로그인 사용자 API가 없어 픽스처 담당자 한 명을 "나"로 둔다 — "내 담당" 필터의 기준이다. */
const CURRENT_USER_NAME = '팀원F';

/**
 * LLM Wiki 대시보드. 목록·집계 API가 없어 픽스처를 렌더한다 —
 * 실 API 도착 시 이 픽스처 자리만 교체한다.
 */
export default function Page() {
  const router = useRouter();

  return (
    <WikiDashboardPage
      stats={REVIEW_STAT_CARD_FIXTURES}
      documents={DOCUMENT_ROW_FIXTURES}
      currentUserName={CURRENT_USER_NAME}
      assigneeOptions={REVIEW_QUEUE_ASSIGNEE_OPTIONS}
      pageSize={PAGE_SIZE}
      onDocumentClick={(documentId) => router.push(`/llm-wiki/${documentId}`)}
    />
  );
}
