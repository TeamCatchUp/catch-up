/** /api/v1/knowledge-review/* 요청 함수. 응답은 서버 DTO 그대로 돌려준다. */

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ReviewBlockVerdictDto,
  ReviewBlockVerdictRequest,
  ReviewProposalDetailDto,
  ReviewPublishDto,
  ReviewPublishRequest,
  ReviewQueuePageDto,
  ReviewQueueParams,
} from './knowledgeReviewDto';

export async function fetchReviewQueue(params: ReviewQueueParams, signal?: AbortSignal): Promise<ReviewQueuePageDto> {
  const res = await api.get<ReviewQueuePageDto>(API.knowledgeReview.queue, { params, signal });
  return res.data;
}

/** 상세는 결정 권한이 없어도 열린다 — 권한 판정은 응답의 can_review로 온다. */
export async function fetchReviewQueueItem(proposalId: string, signal?: AbortSignal): Promise<ReviewProposalDetailDto> {
  const res = await api.get<ReviewProposalDetailDto>(API.knowledgeReview.queueItem(proposalId), { signal });
  return res.data;
}

/** 블록 판정(PUT, 멱등). 블록 자리는 경로로 가고 본문에는 남지 않는다. */
export async function submitReviewBlockVerdict(
  proposalId: string,
  blockIndex: number,
  body: ReviewBlockVerdictRequest,
): Promise<ReviewBlockVerdictDto> {
  const res = await api.put<ReviewBlockVerdictDto>(API.knowledgeReview.blockVerdict(proposalId, blockIndex), body);
  return res.data;
}

export async function clearReviewBlockVerdict(proposalId: string, blockIndex: number): Promise<void> {
  await api.delete(API.knowledgeReview.blockVerdict(proposalId, blockIndex));
}

/** 발행. 블록 판정이 남아 있으면 서버가 UNDECIDED_BLOCKS로 막는다. */
export async function publishReviewProposal(proposalId: string, body: ReviewPublishRequest): Promise<ReviewPublishDto> {
  const res = await api.post<ReviewPublishDto>(API.knowledgeReview.publish(proposalId), body);
  return res.data;
}
