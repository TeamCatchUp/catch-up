import { useMutation, useQueryClient } from '@tanstack/react-query';

import { parseApiError } from '@/shared/api/errors';
import { toast } from '@/shared/components/ui/toast';

import { moveWikiArtifact } from '../api/wikiRequests';
import { wikiQueries } from './wiki.queries';

export interface MoveWikiArtifactVariables {
  /** 이동은 artifact 단위다 — 채널·폴더에는 대응 경로가 없다 */
  artifactId: string;
  /** 대상 폴더. null이면 채널 바로 아래다 */
  folderId: string | null;
}

/**
 * 문서 폴더 이동. 성공 시 위키 뿌리를 무효화한다 —
 * 채널 응답의 폴더 구성과 문서 목록의 folder_id가 함께 바뀐다.
 */
export const useMoveWikiArtifactMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ artifactId, folderId }: MoveWikiArtifactVariables): Promise<void> =>
      moveWikiArtifact(artifactId, folderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: wikiQueries.all() });
    },
    // 검수 자격이 없으면 403이 온다 — 서버 문구를 그대로 띄운다
    onError: (error) => {
      toast(parseApiError(error).message);
    },
  });
};
