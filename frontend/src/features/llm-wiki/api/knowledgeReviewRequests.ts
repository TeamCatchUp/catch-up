/** GET /api/v1/knowledge-review/* 요청 함수. 응답은 서버 DTO 그대로 돌려준다. */

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { ReviewProposalDetailDto, ReviewQueuePageDto, ReviewQueueParams } from './knowledgeReviewDto';

export async function fetchReviewQueue(params: ReviewQueueParams, signal?: AbortSignal): Promise<ReviewQueuePageDto> {
  const res = await api.get<ReviewQueuePageDto>(API.knowledgeReview.queue, { params, signal });
  return res.data;
}

/** 상세는 결정 권한이 없어도 열린다 — 권한 판정은 응답의 can_review로 온다. */
export async function fetchReviewQueueItem(proposalId: string, signal?: AbortSignal): Promise<ReviewProposalDetailDto> {
  const res = await api.get<ReviewProposalDetailDto>(API.knowledgeReview.queueItem(proposalId), { signal });
  return res.data;
}
