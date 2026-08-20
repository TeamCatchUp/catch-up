import { useMutation, useQueryClient } from '@tanstack/react-query';

import { parseApiError } from '@/shared/api/errors';
import { toast } from '@/shared/components/ui/toast';

import { addWikiFavorite, removeWikiFavorite } from '../api/wikiRequests';
import { wikiQueries } from './wiki.queries';

export interface WikiFavoriteToggleVariables {
  /** 즐겨찾기는 문서(artifact) 단위다 — 채널·폴더에는 대응 경로가 없다 */
  artifactId: string;
  /** true면 등록(PUT), false면 해제(DELETE). 둘 다 멱등이라 중복 호출이 안전하다 */
  favorite: boolean;
}

/**
 * 즐겨찾기 등록·해제. 등록과 해제가 같은 자리를 뒤집어 한 훅으로 둔다.
 * 성공 시 위키 뿌리를 무효화한다 — 즐겨찾기 섹션과 문서 행의 별 상태가 함께 바뀐다.
 */
export const useWikiFavoriteToggleMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ artifactId, favorite }: WikiFavoriteToggleVariables): Promise<void> =>
      favorite ? addWikiFavorite(artifactId) : removeWikiFavorite(artifactId),
    onSuccess: () => {
      // all()이 favorites·artifacts 키를 모두 덮는다 — 문서 목록의 is_favorite도 여기서 다시 온다
      queryClient.invalidateQueries({ queryKey: wikiQueries.all() });
    },
    onError: (error) => {
      toast(parseApiError(error).message);
    },
  });
};
