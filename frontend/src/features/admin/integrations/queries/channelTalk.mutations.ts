import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ChannelTalkConnectResponse,
  ChannelTalkCredentialRequest,
  ChannelTalkDocumentConnectResponse,
  ChannelTalkDocumentCredentialRequest,
  ChannelTalkDocumentUninstallResponse,
  ChannelTalkDocumentValidateResponse,
  ChannelTalkUninstallResponse,
  ChannelTalkValidateResponse,
} from '../types/channelTalkApi';
import { adminConnectorQueries } from './adminConnector.queries';

const CHANNEL_TALK_CONNECTION_STATUS_KEY = ['integrations', 'channel_talk', 'connection-status'] as const;

// "연결 테스트하기" 버튼은 validate → save 두 단계를 순차 실행 (mutationFn 내부 chain)
// validate 실패 시 save 호출 안 함, save 실패는 네트워크/서버 이슈
// meta.invalidates로 channel_talk connection-status 캐시 자동 갱신
export const channelTalkMutations = {
  // 채널 credential validate + save
  saveChannelCredential: () =>
    ({
      mutationKey: ['admin', 'connector', 'channelTalk', 'saveChannel'] as const,
      mutationFn: async (body: ChannelTalkCredentialRequest): Promise<AxiosResponse<ChannelTalkConnectResponse>> => {
        await api.post<ChannelTalkValidateResponse>(API.admin.connector.channelTalk.credentialsValidate, body);
        return api.post<ChannelTalkConnectResponse>(API.admin.connector.channelTalk.credentials, body);
      },
      meta: {
        invalidates: [[...CHANNEL_TALK_CONNECTION_STATUS_KEY], [...adminConnectorQueries.all(), 'targetStatus']],
      },
    }) satisfies UseMutationOptions<AxiosResponse<ChannelTalkConnectResponse>, Error, ChannelTalkCredentialRequest>,

  // 도큐먼트 스페이스 credential validate + save
  saveDocumentCredential: () =>
    ({
      mutationKey: ['admin', 'connector', 'channelTalk', 'saveDocument'] as const,
      mutationFn: async (
        body: ChannelTalkDocumentCredentialRequest,
      ): Promise<AxiosResponse<ChannelTalkDocumentConnectResponse>> => {
        await api.post<ChannelTalkDocumentValidateResponse>(
          API.admin.connector.channelTalk.documentCredentialsValidate,
          body,
        );
        return api.post<ChannelTalkDocumentConnectResponse>(API.admin.connector.channelTalk.documentCredentials, body);
      },
      meta: {
        invalidates: [[...CHANNEL_TALK_CONNECTION_STATUS_KEY], [...adminConnectorQueries.all(), 'targetStatus']],
      },
    }) satisfies UseMutationOptions<
      AxiosResponse<ChannelTalkDocumentConnectResponse>,
      Error,
      ChannelTalkDocumentCredentialRequest
    >,

  // DELETE /credentials?channel_id=X
  deleteChannelCredential: () =>
    ({
      mutationKey: ['admin', 'connector', 'channelTalk', 'deleteChannel'] as const,
      mutationFn: (channelId: string) =>
        api.delete<ChannelTalkUninstallResponse>(API.admin.connector.channelTalk.credentials, {
          params: { channel_id: channelId },
        }),
      meta: {
        invalidates: [[...CHANNEL_TALK_CONNECTION_STATUS_KEY], [...adminConnectorQueries.all(), 'targetStatus']],
      },
    }) satisfies UseMutationOptions<AxiosResponse<ChannelTalkUninstallResponse>, Error, string>,

  // DELETE /documents/credentials?space_id=X
  deleteDocumentCredential: () =>
    ({
      mutationKey: ['admin', 'connector', 'channelTalk', 'deleteDocument'] as const,
      mutationFn: (spaceId: string) =>
        api.delete<ChannelTalkDocumentUninstallResponse>(API.admin.connector.channelTalk.documentCredentials, {
          params: { space_id: spaceId },
        }),
      meta: {
        invalidates: [[...CHANNEL_TALK_CONNECTION_STATUS_KEY], [...adminConnectorQueries.all(), 'targetStatus']],
      },
    }) satisfies UseMutationOptions<AxiosResponse<ChannelTalkDocumentUninstallResponse>, Error, string>,
};
