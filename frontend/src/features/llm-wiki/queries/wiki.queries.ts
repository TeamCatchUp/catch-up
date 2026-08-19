import { queryOptions } from '@tanstack/react-query';

import type { WikiArtifactListParams } from '../api/wikiDto';
import {
  fetchWikiArtifactDocument,
  fetchWikiArtifacts,
  fetchWikiChannels,
  fetchWikiDefinitionPresets,
  fetchWikiFavorites,
  fetchWikiMembers,
} from '../api/wikiRequests';

/** 키 앞단은 ['llm-wiki']로 맞춘다 — 검수 루프와 함께 한 번에 무효화할 수 있어야 한다. */
export const wikiQueries = {
  all: () => ['llm-wiki', 'wiki'] as const,

  /** 채널 목록. 경로 join의 이름 공급원이라 문서 목록보다 오래 신선하게 둔다. */
  channels: () =>
    queryOptions({
      queryKey: [...wikiQueries.all(), 'channels'] as const,
      queryFn: ({ signal }) => fetchWikiChannels(signal),
      staleTime: 5 * 60_000,
    }),

  /** preset 카탈로그. 서버 코드 안의 상수라 workspace마다 달라지지 않는다. */
  definitionPresets: () =>
    queryOptions({
      queryKey: [...wikiQueries.all(), 'definition-presets'] as const,
      queryFn: ({ signal }) => fetchWikiDefinitionPresets(signal),
      staleTime: Infinity,
    }),

  /** 담당자 피커 후보. 워크스페이스 하나 규모라 쪽을 나누지 않고 채널 목록과 같은 신선도로 둔다. */
  members: () =>
    queryOptions({
      queryKey: [...wikiQueries.all(), 'members'] as const,
      queryFn: ({ signal }) => fetchWikiMembers(signal),
      staleTime: 5 * 60_000,
    }),

  artifacts: (params: WikiArtifactListParams = {}) =>
    queryOptions({
      queryKey: [...wikiQueries.all(), 'artifacts', params] as const,
      queryFn: ({ signal }) => fetchWikiArtifacts(params, signal),
      staleTime: 30_000,
    }),

  /** 발행판 상세. 발행된 판이 없는 문서는 404라 에러 분기가 정상 경로다. */
  artifact: (artifactId: string) =>
    queryOptions({
      queryKey: [...wikiQueries.all(), 'artifact', artifactId] as const,
      queryFn: ({ signal }) => fetchWikiArtifactDocument(artifactId, signal),
      enabled: artifactId.length > 0,
      staleTime: 30_000,
    }),

  favorites: () =>
    queryOptions({
      queryKey: [...wikiQueries.all(), 'favorites'] as const,
      queryFn: ({ signal }) => fetchWikiFavorites(signal),
      staleTime: 30_000,
    }),
};
