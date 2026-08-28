import { useMutation, useQueryClient } from '@tanstack/react-query';

import { parseApiError } from '@/shared/api/errors';
import { toast } from '@/shared/components/ui/toast';

import { moveWikiArtifact } from '../api/wikiRequests';
import { invalidateWikiLocationCaches } from './wikiLocationInvalidation';

export interface MoveWikiArtifactVariables {
  /** 이동은 artifact 단위다 — 채널·폴더에는 대응 경로가 없다 */
  artifactId: string;
  /** 대상 폴더. null이면 채널 바로 아래다 */
  folderId: string | null;
}

/**
 * 문서 폴더 이동. 위치를 실은 캐시만 되돌린다 — 옮긴 문서의 상세(breadcrumb)까지 포함이다.
 * 구성원·definition-presets는 이동으로 바뀌지 않아 뿌리째 무효화하지 않는다.
 */
export const useMoveWikiArtifactMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ artifactId, folderId }: MoveWikiArtifactVariables): Promise<void> =>
      moveWikiArtifact(artifactId, folderId),
    onSuccess: (_data, { artifactId }) => {
      invalidateWikiLocationCaches(queryClient, artifactId);
    },
    // 검수 자격이 없으면 403이 온다 — 서버 문구를 그대로 띄운다
    onError: (error) => {
      toast(parseApiError(error).message);
    },
  });
};
