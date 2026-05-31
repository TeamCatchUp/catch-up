import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type { SourceTypeApi } from '@/shared/types/sourceApi';

import type {
  ChannelTalkOriginalContentResponse,
  OriginalContentRequest,
} from '../types/originalApi';

interface DetailParams {
  connector: SourceTypeApi;
  entityType: string;
  documentId: string;
}

export const originalContentQueries = {
  all: () => ['search', 'original'] as const,
  details: () => [...originalContentQueries.all(), 'detail'] as const,

  // 원문 대화 — connector + documentId에만 의존. 첫 페이지만 조회(next_cursor 미포함).
  // ChannelTalk user_chat이 아니면 disabled — 그 외 소스는 패널이 Coming Soon을 표시.
  detail: (params: DetailParams) =>
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
      enabled: Boolean(
        params.documentId &&
          params.connector === 'channel_talk' &&
          params.entityType === 'user_chat',
      ),
      staleTime: 5 * 60_000,
    }),
};
