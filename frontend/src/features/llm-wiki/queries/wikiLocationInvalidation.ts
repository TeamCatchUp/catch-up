import type { QueryClient } from '@tanstack/react-query';

import { knowledgeReviewQueries } from './knowledgeReview.queries';
import { wikiQueries } from './wiki.queries';

/**
 * 문서 위치를 실은 캐시를 되돌린다 — 채널 트리·문서 목록·문서 상세·즐겨찾기·검토큐.
 * artifactId를 알면 그 문서 상세만, 모르면(폴더 삭제 대량 이동) 상세 전체를 겨눈다.
 */
export function invalidateWikiLocationCaches(queryClient: QueryClient, artifactId?: string) {
  queryClient.invalidateQueries({ queryKey: wikiQueries.channels().queryKey });
  queryClient.invalidateQueries({ queryKey: [...wikiQueries.all(), 'artifacts'] });
  queryClient.invalidateQueries({
    queryKey: artifactId === undefined ? wikiQueries.artifactRoot() : wikiQueries.artifact(artifactId).queryKey,
  });
  queryClient.invalidateQueries({ queryKey: wikiQueries.favorites().queryKey });
  queryClient.invalidateQueries({ queryKey: knowledgeReviewQueries.all() });
}
