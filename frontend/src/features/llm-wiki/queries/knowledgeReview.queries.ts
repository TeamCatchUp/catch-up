import { queryOptions } from '@tanstack/react-query';

import type { ReviewQueueParams } from '../api/knowledgeReviewDto';
import { fetchReviewQueue, fetchReviewQueueItem } from '../api/knowledgeReviewRequests';

/** 검수 루프 큐. 키 앞단을 ['llm-wiki']로 맞춰 위키 쪽과 함께 무효화할 수 있게 둔다. */
export const knowledgeReviewQueries = {
  all: () => ['llm-wiki', 'knowledge-review'] as const,

  /** 큐는 판정으로 줄이 빠지는 목록이라 문서 목록보다 짧게 잡는다. */
  queue: (params: ReviewQueueParams = {}) =>
    queryOptions({
      queryKey: [...knowledgeReviewQueries.all(), 'queue', params] as const,
      queryFn: ({ signal }) => fetchReviewQueue(params, signal),
      staleTime: 15_000,
    }),

  /** 상세는 결정 권한이 없어도 열린다 — 응답의 can_review로 버튼만 잠근다. */
  queueItem: (proposalId: string) =>
    queryOptions({
      queryKey: [...knowledgeReviewQueries.all(), 'queue', 'item', proposalId] as const,
      queryFn: ({ signal }) => fetchReviewQueueItem(proposalId, signal),
      enabled: proposalId.length > 0,
      staleTime: 15_000,
    }),
};
