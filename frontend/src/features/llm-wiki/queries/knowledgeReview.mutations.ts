import { type QueryClient, useMutation, useQueryClient } from '@tanstack/react-query';

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
import { publishReviewProposal, rejectReviewProposal, submitReviewBlockVerdict } from '../api/knowledgeReviewRequests';
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

/** 일괄 승인이 보낼 블록 하나. 판정 경로가 있는 카드만 여기 담긴다 */
export interface BlockApproveTarget {
  blockIndex: number;
  block_content_hash: string;
}

/** 일괄 승인 결과. 일부만 실패해도 성공분은 서버에 남는다 */
export interface BulkApproveResult {
  requested: number;
  failed: number;
  /** 첫 실패의 서버 문구. 전부 성공하면 null */
  message: string | null;
}

/**
 * 판정이 바꾸는 위키 캐시 — 문서 목록(상태·최근 활동)과 그 문서의 발행판뿐이다.
 * 채널·구성원·preset은 판정으로 바뀌지 않아 뿌리째 무효화하지 않는다.
 */
function invalidateWikiArtifacts(queryClient: QueryClient, artifactId?: string) {
  queryClient.invalidateQueries({ queryKey: [...wikiQueries.all(), 'artifacts'] });
  // 문서 id를 아직 모르는 화면(상세 도착 전)은 목록만 되돌린다
  if (artifactId) queryClient.invalidateQueries({ queryKey: wikiQueries.artifact(artifactId).queryKey });
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

/**
 * 블록 판정 일괄 전송(승인). 개별 판정과 같은 PUT을 병렬로 보내고 성패를 세어 돌려준다.
 * 일부만 실패해도 상세를 다시 읽는다 — 성공분의 판정이 카드에 서야 한다.
 */
export const useReviewBulkApproveMutation = (proposalId: string) => {
  const queryClient = useQueryClient();
  const detailKey = knowledgeReviewQueries.queueItem(proposalId).queryKey;

  return useMutation({
    mutationFn: async (targets: readonly BlockApproveTarget[]): Promise<BulkApproveResult> => {
      const settled = await Promise.allSettled(
        targets.map(({ blockIndex, block_content_hash }) =>
          submitReviewBlockVerdict(proposalId, blockIndex, { verdict: 'approved', block_content_hash }),
        ),
      );
      const rejected = settled.filter((result): result is PromiseRejectedResult => result.status === 'rejected');

      return {
        requested: targets.length,
        failed: rejected.length,
        message: rejected.length > 0 ? parseApiError(rejected[0].reason).message : null,
      };
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: detailKey });
    },
  });
};

/** 발행. 큐에서 줄이 빠지고 문서 쪽 상태·최근 활동이 함께 바뀌어 큐 뿌리와 문서 캐시를 되돌린다. */
export const useReviewPublishMutation = (proposalId: string, artifactId?: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: ReviewPublishRequest): Promise<ReviewPublishDto> => publishReviewProposal(proposalId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: knowledgeReviewQueries.all() });
      invalidateWikiArtifacts(queryClient, artifactId);
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
export const useRejectReviewProposalMutation = (proposalId: string, artifactId?: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: ReviewRejectRequest): Promise<ReviewDecisionDto> => rejectReviewProposal(proposalId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: knowledgeReviewQueries.all() });
      invalidateWikiArtifacts(queryClient, artifactId);
    },
    onError: (error) => {
      toast(parseApiError(error).message, REVIEW_TOAST_OPTIONS);
    },
  });
};
