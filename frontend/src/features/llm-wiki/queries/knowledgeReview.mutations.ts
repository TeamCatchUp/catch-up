import { useMutation, useQueryClient } from '@tanstack/react-query';

import { parseApiError } from '@/shared/api/errors';
import { toast } from '@/shared/components/ui/toast';

import type {
  ReviewBlockVerdictDto,
  ReviewBlockVerdictRequest,
  ReviewDecisionDto,
  ReviewPublishDto,
  ReviewPublishRequest,
  ReviewRejectRequest,
} from '../api/knowledgeReviewDto';
import {
  approveReviewProposal,
  publishReviewProposal,
  rejectReviewProposal,
  submitReviewBlockVerdict,
} from '../api/knowledgeReviewRequests';
import { knowledgeReviewQueries } from './knowledgeReview.queries';
import { wikiQueries } from './wiki.queries';

/** 블록 판정이 낡은 상태로 막히는 코드. 재조회가 곧 복구다 */
const BLOCK_VERDICT_STALE_CODES = ['STALE_BLOCK', 'ALREADY_DECIDED'];

/** 발행이 낡은 상태로 막히는 코드. 블록 판정에는 없는 미결정·모순 경합이 더 온다 */
const PUBLISH_STALE_CODES = ['STALE_BLOCK', 'ALREADY_DECIDED', 'UNDECIDED_BLOCKS', 'CONFLICT_RACE'];

/** 검토 큐 토스트만 우하단에 띄운다 — 전역 Toaster(하단 중앙)는 그대로 둔다 */
export const REVIEW_TOAST_OPTIONS = { position: 'bottom-right' } as const;

interface BlockVerdictVariables extends ReviewBlockVerdictRequest {
  /** 경로에 실리는 블록 자리. 화면이 본 블록의 값을 그대로 보낸다 */
  blockIndex: number;
}

/**
 * 블록 판정(PUT, 멱등). 성공·실패 모두 상세만 다시 읽는다 —
 * 큐 줄은 블록 판정으로 바뀌지 않고, 실패 대부분이 낡은 지문이라 재조회가 곧 복구다.
 */
export const useReviewBlockVerdictMutation = (proposalId: string) => {
  const queryClient = useQueryClient();
  const detailKey = knowledgeReviewQueries.queueItem(proposalId).queryKey;

  return useMutation({
    mutationFn: ({ blockIndex, ...body }: BlockVerdictVariables): Promise<ReviewBlockVerdictDto> =>
      submitReviewBlockVerdict(proposalId, blockIndex, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: detailKey });
    },
    onError: (error) => {
      const { code, message } = parseApiError(error);
      toast(message, REVIEW_TOAST_OPTIONS);
      if (BLOCK_VERDICT_STALE_CODES.includes(code)) queryClient.invalidateQueries({ queryKey: detailKey });
    },
  });
};

/** 발행. 큐에서 줄이 빠지고 문서 쪽 상태·최근 활동이 함께 바뀌어 두 뿌리를 모두 무효화한다. */
export const useReviewPublishMutation = (proposalId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: ReviewPublishRequest): Promise<ReviewPublishDto> => publishReviewProposal(proposalId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: knowledgeReviewQueries.all() });
      queryClient.invalidateQueries({ queryKey: wikiQueries.all() });
    },
    onError: (error) => {
      const { code, message } = parseApiError(error);
      toast(message, REVIEW_TOAST_OPTIONS);
      if (PUBLISH_STALE_CODES.includes(code)) {
        queryClient.invalidateQueries({ queryKey: knowledgeReviewQueries.queueItem(proposalId).queryKey });
      }
    },
  });
};

/**
 * 변경안 통째 반려. 사유가 비면 서버가 400으로 막는다.
 * 블록 판정이 시작된 변경안에는 쓸 수 없어 진입점은 판정 전 화면에만 놓을 수 있다.
 */
export const useRejectReviewProposalMutation = (proposalId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: ReviewRejectRequest): Promise<ReviewDecisionDto> => rejectReviewProposal(proposalId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: knowledgeReviewQueries.all() });
      queryClient.invalidateQueries({ queryKey: wikiQueries.all() });
    },
    onError: (error) => {
      toast(parseApiError(error).message, REVIEW_TOAST_OPTIONS);
    },
  });
};

/**
 * 변경안 통째 승인. 새 revision이 발행되므로 큐와 문서 쪽을 함께 무효화한다.
 * 블록 판정이 시작된 변경안은 서버가 409로 막고, 그 메시지를 토스트로 보인다.
 */
export const useApproveReviewProposalMutation = (proposalId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (): Promise<ReviewDecisionDto> => approveReviewProposal(proposalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: knowledgeReviewQueries.all() });
      queryClient.invalidateQueries({ queryKey: wikiQueries.all() });
    },
    onError: (error) => {
      toast(parseApiError(error).message, REVIEW_TOAST_OPTIONS);
    },
  });
};
