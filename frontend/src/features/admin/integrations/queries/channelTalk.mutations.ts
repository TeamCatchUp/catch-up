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
import { channelTalkQueries } from './channelTalk.queries';

/**
 * 채널톡 mutation.
 *
 * 백엔드는 validate(검증)와 save(upsert)가 분리된 두 엔드포인트지만,
 * UX 결정에 따라 "연결 테스트하기" 버튼 한 번에 두 단계를 순차 실행.
 * mutationFn 내부에서 validate → save로 chain.
 *
 * 실패 분기:
 * - validate 실패 → save 호출 안 함, validate 에러를 throw (호출처에서 parseApiError로 메시지 추출)
 * - save 실패 → save 에러를 throw (이미 validate 통과한 키이므로 네트워크/서버 이슈일 가능성)
 *
 * 캐시 무효화: meta.invalidates로 channelTalkQueries.all() 키 하위 모두 무효화 → detail/documentDetail 자동 refetch.
 */
export const channelTalkMutations = {
  /** 채널 credential validate + save 통합 mutation */
  saveChannelCredential: () =>
    ({
      mutationKey: ['admin', 'connector', 'channelTalk', 'saveChannel'] as const,
      mutationFn: async (body: ChannelTalkCredentialRequest): Promise<AxiosResponse<ChannelTalkConnectResponse>> => {
        // Step 1: validate — 실패 시 여기서 throw, save는 호출 안 됨
        await api.post<ChannelTalkValidateResponse>(API.admin.connector.channelTalk.credentialsValidate, body);
        // Step 2: save (upsert)
        return api.post<ChannelTalkConnectResponse>(API.admin.connector.channelTalk.credentials, body);
      },
      meta: { invalidates: [[...channelTalkQueries.all()], [...adminConnectorQueries.all(), 'targetStatus']] },
    }) satisfies UseMutationOptions<AxiosResponse<ChannelTalkConnectResponse>, Error, ChannelTalkCredentialRequest>,

  /** 도큐먼트 스페이스 credential validate + save 통합 mutation */
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
      meta: { invalidates: [[...channelTalkQueries.all()], [...adminConnectorQueries.all(), 'targetStatus']] },
    }) satisfies UseMutationOptions<
      AxiosResponse<ChannelTalkDocumentConnectResponse>,
      Error,
      ChannelTalkDocumentCredentialRequest
    >,

  /** DELETE /credentials?channel_id=X — 채널 credential 개별 삭제 */
  deleteChannelCredential: () =>
    ({
      mutationKey: ['admin', 'connector', 'channelTalk', 'deleteChannel'] as const,
      mutationFn: (channelId: string) =>
        api.delete<ChannelTalkUninstallResponse>(API.admin.connector.channelTalk.credentials, {
          params: { channel_id: channelId },
        }),
      meta: { invalidates: [[...channelTalkQueries.all()], [...adminConnectorQueries.all(), 'targetStatus']] },
    }) satisfies UseMutationOptions<AxiosResponse<ChannelTalkUninstallResponse>, Error, string>,

  /** DELETE /documents/credentials?space_id=X — 도큐먼트 스페이스 credential 개별 삭제 */
  deleteDocumentCredential: () =>
    ({
      mutationKey: ['admin', 'connector', 'channelTalk', 'deleteDocument'] as const,
      mutationFn: (spaceId: string) =>
        api.delete<ChannelTalkDocumentUninstallResponse>(API.admin.connector.channelTalk.documentCredentials, {
          params: { space_id: spaceId },
        }),
      meta: { invalidates: [[...channelTalkQueries.all()], [...adminConnectorQueries.all(), 'targetStatus']] },
    }) satisfies UseMutationOptions<AxiosResponse<ChannelTalkDocumentUninstallResponse>, Error, string>,
};
