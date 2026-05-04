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
 * - all                                  : ['admin', 'connector', 'channelTalk']
 * - list (channel credentials)           : [...all, 'list']
 * - documentList (space credentials)     : [...all, 'documents']
 *
 * 백엔드는 같은 channel_id 중복은 막지만 다른 channel_id로는 N개 등록 가능.
 * Document space는 channel당 N개 가능. 두 GET 모두 list 응답.
 *
 * mutation의 meta.invalidates에서 위 키들을 사용해 캐시 무효화.
 */
export const channelTalkQueries = {
  all: () => ['admin', 'connector', 'channelTalk'] as const,

  /** GET /api/v1/admin/connector/channel-talk/credentials — 등록된 채널 credential 목록 */
  list: () =>
    queryOptions({
      queryKey: [...channelTalkQueries.all(), 'list'] as const,
      queryFn: async (): Promise<ChannelTalkStatusResponse[]> => {
        const res = await api.get<ChannelTalkStatusResponse[]>(API.admin.connector.channelTalk.credentials);
        return res.data;
      },
    }),

  /** GET /api/v1/admin/connector/channel-talk/documents/credentials — 등록된 도큐먼트 스페이스 credential 목록 */
  documentList: () =>
    queryOptions({
      queryKey: [...channelTalkQueries.all(), 'documents'] as const,
      queryFn: async (): Promise<ChannelTalkDocumentStatusResponse[]> => {
        const res = await api.get<ChannelTalkDocumentStatusResponse[]>(
          API.admin.connector.channelTalk.documentCredentials,
        );
        return res.data;
      },
    }),
};
