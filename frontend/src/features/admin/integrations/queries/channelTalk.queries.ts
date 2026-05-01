import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ChannelTalkDocumentStatusResponse,
  ChannelTalkStatusResponse,
} from '../types/channelTalkApi';

/**
 * 채널톡 connector queryOptions 팩토리.
 *
 * 키 계층:
 * - all                              : ['admin', 'connector', 'channelTalk']
 * - detail (channel credential)      : [...all, 'detail']
 * - documentDetail (space credential): [...all, 'document']
 *
 * mutation의 meta.invalidates에서 위 키들을 사용해 캐시 무효화.
 */
export const channelTalkQueries = {
  all: () => ['admin', 'connector', 'channelTalk'] as const,

  /** GET /api/v1/admin/connector/channel-talk/credentials — 채널 credential 상태 */
  detail: () =>
    queryOptions({
      queryKey: [...channelTalkQueries.all(), 'detail'] as const,
      queryFn: async (): Promise<ChannelTalkStatusResponse> => {
        const res = await api.get<ChannelTalkStatusResponse>(API.admin.connector.channelTalk.credentials);
        return res.data;
      },
    }),

  /** GET /api/v1/admin/connector/channel-talk/documents/credentials — 도큐먼트 스페이스 credential 상태 */
  documentDetail: () =>
    queryOptions({
      queryKey: [...channelTalkQueries.all(), 'document'] as const,
      queryFn: async (): Promise<ChannelTalkDocumentStatusResponse> => {
        const res = await api.get<ChannelTalkDocumentStatusResponse>(
          API.admin.connector.channelTalk.documentCredentials,
        );
        return res.data;
      },
    }),
};
