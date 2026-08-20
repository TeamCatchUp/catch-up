'use client';

import ReviewQueuePage from '@/features/llm-wiki/components/review-queue/ReviewQueuePage';
import { useReviewQueueModel } from '@/features/llm-wiki/hooks/useReviewQueueModel';

/** LLM Wiki 검토 큐. 조회 상태와 판정·발행 요청은 페이지 모델 훅이 갖고 화면은 받아 그린다. */
export default function Page() {
  const model = useReviewQueueModel();

  return <ReviewQueuePage {...model} />;
}
