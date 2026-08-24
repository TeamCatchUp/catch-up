import { type QueryClient, useMutation, useQueryClient } from '@tanstack/react-query';

import { parseApiError } from '@/shared/api/errors';
import { toast } from '@/shared/components/ui/toast';

import { assignWikiArtifactOwner, removeWikiArtifactOwner } from '../api/wikiRequests';
import { knowledgeReviewQueries } from './knowledgeReview.queries';
import { wikiQueries } from './wiki.queries';

export interface AssignWikiArtifactOwnersVariables {
  artifactId: string;
  /** 지정 대상. 추가 드롭다운의 다중 선택이라 여러 명이 한 번에 온다 */
  userIds: readonly number[];
}

export interface RemoveWikiArtifactOwnerVariables {
  artifactId: string;
  userId: number;
}

/**
 * 담당자 변경이 바꾸는 캐시 전부 — 큐 목록 행·상세(can_review가 함께 바뀐다)와
 * 문서 목록 행·발행판의 owners다. 채널·구성원은 바뀌지 않아 뿌리째 되돌리지 않는다.
 */
function invalidateOwnerConsumers(queryClient: QueryClient, artifactId: string) {
  queryClient.invalidateQueries({ queryKey: knowledgeReviewQueries.all() });
  queryClient.invalidateQueries({ queryKey: [...wikiQueries.all(), 'artifacts'] });
  queryClient.invalidateQueries({ queryKey: wikiQueries.artifact(artifactId).queryKey });
}

/**
 * 담당자 지정(PUT, 멱등). 선택분만큼 병렬로 보내고 하나라도 실패하면 서버 문구를 띄운다 —
 * 부분 성공이 서버에 남을 수 있어 성패와 무관하게 캐시를 되돌린다.
 */
export const useAssignWikiArtifactOwnersMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ artifactId, userIds }: AssignWikiArtifactOwnersVariables) =>
      Promise.all(userIds.map((userId) => assignWikiArtifactOwner(artifactId, userId))),
    onSettled: (_data, _error, { artifactId }) => {
      invalidateOwnerConsumers(queryClient, artifactId);
    },
    // 자격이 없으면 403(NOT_OWNER_MANAGER)이 온다 — 서버 문구를 그대로 띄운다
    onError: (error) => {
      toast(parseApiError(error).message);
    },
  });
};

/** 담당자 해제(DELETE, 멱등·관리자만). 성공 시각은 시안에 없어 캐시만 되돌린다. */
export const useRemoveWikiArtifactOwnerMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ artifactId, userId }: RemoveWikiArtifactOwnerVariables) =>
      removeWikiArtifactOwner(artifactId, userId),
    onSuccess: (_data, { artifactId }) => {
      invalidateOwnerConsumers(queryClient, artifactId);
    },
    onError: (error) => {
      toast(parseApiError(error).message);
    },
  });
};
