import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type { SourceTypeApi } from '@/shared/types/sourceApi';

import type {
  ChannelTalkOriginalContentResponse,
  OriginalContentRequest,
} from '../types/originalApi';
import type { SlackOriginalContentResponse } from '../types/slackOriginalApi';

interface DetailParams {
  connector: SourceTypeApi;
  entityType: string;
  documentId: string;
}

function isChannelTalkUserChat(params: DetailParams): boolean {
  return Boolean(
    params.documentId &&
      params.connector === 'channel_talk' &&
      params.entityType === 'user_chat',
  );
}

function isSlackMessage(params: DetailParams): boolean {
  return Boolean(
    params.documentId && params.connector === 'slack' && params.entityType === 'message',
  );
}

export const originalContentQueries = {
  all: () => ['search', 'original'] as const,
  details: () => [...originalContentQueries.all(), 'detail'] as const,
  infiniteDetails: () => [...originalContentQueries.all(), 'infinite-detail'] as const,

  // 원문 대화 — connector + documentId에만 의존. 첫 페이지만 조회(next_cursor 미포함).
  // ChannelTalk user_chat이 아니면 disabled — 그 외 소스는 패널이 Coming Soon을 표시.
  channelTalkDetail: (params: DetailParams) =>
    queryOptions({
      queryKey: [
        ...originalContentQueries.details(),
        params.connector,
        params.documentId,
      ] as const,
      queryFn: async (): Promise<ChannelTalkOriginalContentResponse> => {
        const body: OriginalContentRequest = {
          connector: params.connector,
          document_id: params.documentId,
        };
        const { data } = await api.post<ChannelTalkOriginalContentResponse>(
          API.search.original,
          body,
        );
        return data;
      },
      enabled: isChannelTalkUserChat(params),
      staleTime: 5 * 60_000,
    }),

  detail: (params: DetailParams) => originalContentQueries.channelTalkDetail(params),

  slackInfinite: (params: DetailParams) =>
    infiniteQueryOptions({
      queryKey: [
        ...originalContentQueries.infiniteDetails(),
        params.connector,
        params.documentId,
      ] as const,
      queryFn: async ({ pageParam }): Promise<SlackOriginalContentResponse> => {
        const body: OriginalContentRequest = {
          connector: 'slack',
          document_id: params.documentId,
          next_cursor: pageParam,
        };
        const { data } = await api.post<SlackOriginalContentResponse>(
          API.search.original,
          body,
        );
        return data;
      },
      initialPageParam: null as string | null,
      getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
      enabled: isSlackMessage(params),
      staleTime: 5 * 60_000,
    }),
};
