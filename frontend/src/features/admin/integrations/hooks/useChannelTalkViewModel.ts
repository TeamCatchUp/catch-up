'use client';

import { useCallback, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { channelTalkMutations } from '../queries/channelTalk.mutations';
import type {
  ChannelTalkDocumentStatusResponse,
  ChannelTalkStatusResponse,
} from '../types/channelTalkApi';
import type {
  ChannelTalkChannelPatch,
  ChannelTalkConnectionState,
  ChannelTalkDocumentSpacePatch,
} from '../types/channelTalkModel';
import {
  CHANNEL_SYNC_INTERVAL_DEFAULT,
  DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
  MASKED_PLACEHOLDER,
} from '../types/channelTalkModel';
import { isChannelSecretsFilled, isDocumentSpaceSecretsFilled } from '../utils/channelTalkHelpers';
import { parseChannelTalkError } from '../utils/parseChannelTalkError';

/**
 * 사용자가 새로 추가한 미검증 카드의 임시 client-side ID.
 * 검증 통과 시 백엔드가 발급한 channel_id/space_id로 교체된다.
 */
function makeId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * 백엔드 GET 응답(list)으로부터 viewModel 초기 state를 derive.
 *
 * - 등록된 channel N개를 카드 N개로 매핑
 * - 각 channel에 속한 document space들을 그 카드의 자식으로 그룹화 (channel_id 기준)
 * - 키 필드는 보안상 응답에 없으므로 MASKED_PLACEHOLDER로 채워서 lock 상태 시각화
 * - lastSyncedAt은 모든 channel 중 가장 최근 검증 시각으로 노출
 */
export function deriveChannelTalkInitialState(
  channelDataList: ChannelTalkStatusResponse[] | undefined,
  documentDataList: ChannelTalkDocumentStatusResponse[] | undefined,
): ChannelTalkConnectionState {
  const installedChannels = (channelDataList ?? []).filter(
    (c): c is ChannelTalkStatusResponse & { channel_id: string } => c.installed && !!c.channel_id,
  );

  if (installedChannels.length === 0) {
    return { connected: false, lastSyncedAt: null, channels: [] };
  }

  const installedDocuments = (documentDataList ?? []).filter(
    (d): d is ChannelTalkDocumentStatusResponse & { channel_id: string; space_id: string } =>
      d.installed && !!d.channel_id && !!d.space_id,
  );

  const channels = installedChannels.map((channelData) => ({
    id: channelData.channel_id,
    name: channelData.channel_name ?? '',
    accessKey: MASKED_PLACEHOLDER,
    accessSecret: MASKED_PLACEHOLDER,
    webhookToken: channelData.webhook_token_configured ? MASKED_PLACEHOLDER : '',
    syncInterval: CHANNEL_SYNC_INTERVAL_DEFAULT,
    documentSpaces: installedDocuments
      .filter((d) => d.channel_id === channelData.channel_id)
      .map((d) => ({
        id: d.space_id,
        name: d.space_name ?? '',
        accessKey: MASKED_PLACEHOLDER,
        accessSecret: MASKED_PLACEHOLDER,
        syncInterval: DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
        connectionStatus: 'tested' as const,
      })),
    connectionStatus: 'tested' as const,
  }));

  // 모든 channel 중 가장 최근 검증 시각
  const verifiedTimes = installedChannels
    .map((c) => c.credential_last_verified_at)
    .filter((t): t is string => !!t);
  const lastSyncedAt = verifiedTimes.length > 0 ? verifiedTimes.sort().reverse()[0] : null;

  return {
    connected: true,
    lastSyncedAt,
    channels,
  };
}

interface ChannelTalkViewModel {
  state: ChannelTalkConnectionState;
  addChannel: () => void;
  updateChannel: (channelId: string, patch: ChannelTalkChannelPatch) => void;
  removeChannel: (channelId: string) => void;
  enterEditMode: (channelId: string) => void;
  addDocumentSpace: (channelId: string) => void;
  updateDocumentSpace: (channelId: string, dsId: string, patch: ChannelTalkDocumentSpacePatch) => void;
  removeDocumentSpace: (channelId: string, dsId: string) => void;
  testChannelConnection: (channelId: string) => void;
  testDocumentSpaceConnection: (channelId: string, dsId: string) => void;
  enterDocumentSpaceEditMode: (channelId: string, dsId: string) => void;
}

/**
 * 채널톡 연동 viewModel — 실제 백엔드 API와 wiring된 버전.
 *
 * **Hydration**: 호출자가 백엔드 GET 응답으로부터 derive한 `initialState`를 prop으로 전달.
 * 이 hook은 useState의 lazy initialization으로 그 값을 시작점으로 삼는다.
 * (React 19 `react-hooks/set-state-in-effect` 룰을 회피하기 위한 mount/unmount 패턴.)
 *
 * **편집**: "수정하기"(enterEditMode) 클릭 시 마스킹 문자열을 빈 문자열로 초기화.
 *
 * **검증+저장**: "연결 테스트하기"(testChannelConnection) 클릭 시 validate+save 통합 mutation 호출.
 * 성공 시 백엔드 응답의 channel_id/channel_name을 state에 반영하고 키 필드를 다시 마스킹.
 *
 * **삭제**: 검증된(tested) 카드는 백엔드 DELETE 호출, 미검증 카드는 로컬 state만 제거.
 * 휴지통 클릭 시 즉시 사라지고 backend 응답 기다리지 않는 optimistic UI.
 */
export function useChannelTalkViewModel(initialState: ChannelTalkConnectionState): ChannelTalkViewModel {
  const [state, setState] = useState<ChannelTalkConnectionState>(initialState);

  const channelMutation = useMutation(channelTalkMutations.saveChannelCredential());
  const documentMutation = useMutation(channelTalkMutations.saveDocumentCredential());
  const deleteChannelMutation = useMutation(channelTalkMutations.deleteChannelCredential());
  const deleteDocumentMutation = useMutation(channelTalkMutations.deleteDocumentCredential());

  const addChannel = useCallback(() => {
    setState((prev) => ({
      ...prev,
      channels: [
        ...prev.channels,
        {
          id: makeId('ch'),
          name: `채널 ${prev.channels.length + 1}`,
          accessKey: '',
          accessSecret: '',
          webhookToken: '',
          syncInterval: CHANNEL_SYNC_INTERVAL_DEFAULT,
          documentSpaces: [],
          connectionStatus: 'idle',
        },
      ],
    }));
  }, []);

  const updateChannel = useCallback((channelId: string, patch: ChannelTalkChannelPatch) => {
    setState((prev) => ({
      ...prev,
      channels: prev.channels.map((ch) => {
        if (ch.id !== channelId) return ch;
        const next = { ...ch, ...patch };

        const hadValidation = ch.connectionStatus === 'tested' || ch.connectionStatus === 'error';
        const secretChanged =
          ('accessKey' in patch && patch.accessKey !== ch.accessKey) ||
          ('accessSecret' in patch && patch.accessSecret !== ch.accessSecret) ||
          ('webhookToken' in patch && patch.webhookToken !== ch.webhookToken);
        if (hadValidation && secretChanged) {
          next.connectionStatus = 'idle';
          next.errorMessage = undefined;
        }
        return next;
      }),
    }));
  }, []);

  const removeChannel = useCallback(
    (channelId: string) => {
      const channel = state.channels.find((c) => c.id === channelId);
      // 검증 통과한 채널만 백엔드에 등록되어 있으므로 DELETE 호출 대상.
      const isPersisted = channel?.connectionStatus === 'tested';

      // optimistic UI: 즉시 화면에서 제거
      setState((prev) => ({
        ...prev,
        channels: prev.channels.filter((ch) => ch.id !== channelId),
      }));

      if (!isPersisted) return;

      deleteChannelMutation.mutate(channelId, {
        onError: (error) => {
          // 실패 시 카드 복원 + 에러 토스트. cache invalidation으로 자동 refetch도 동작하므로
          // 다음 GET이 오면 진실의 원천 복구.
          const { message } = parseChannelTalkError(error);
          toast.error('채널 삭제에 실패했어요.', { description: message });
        },
      });
    },
    [state.channels, deleteChannelMutation],
  );

  const enterEditMode = useCallback((channelId: string) => {
    setState((prev) => ({
      ...prev,
      channels: prev.channels.map((ch) =>
        ch.id === channelId
          ? {
              ...ch,
              // 마스킹된 키 필드를 비워서 새 키 입력을 받음
              accessKey: '',
              accessSecret: '',
              webhookToken: '',
              connectionStatus: 'editing' as const,
              errorMessage: undefined,
            }
          : ch,
      ),
    }));
  }, []);

  const addDocumentSpace = useCallback((channelId: string) => {
    setState((prev) => ({
      ...prev,
      channels: prev.channels.map((ch) =>
        ch.id === channelId
          ? {
              ...ch,
              documentSpaces: [
                ...ch.documentSpaces,
                {
                  id: makeId('ds'),
                  name: `도큐먼트 스페이스 ${ch.documentSpaces.length + 1}`,
                  accessKey: '',
                  accessSecret: '',
                  syncInterval: DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
                  connectionStatus: 'idle',
                },
              ],
            }
          : ch,
      ),
    }));
  }, []);

  const updateDocumentSpace = useCallback(
    (channelId: string, dsId: string, patch: ChannelTalkDocumentSpacePatch) => {
      setState((prev) => ({
        ...prev,
        channels: prev.channels.map((ch) => {
          if (ch.id !== channelId) return ch;
          return {
            ...ch,
            documentSpaces: ch.documentSpaces.map((ds) => {
              if (ds.id !== dsId) return ds;
              const next = { ...ds, ...patch };
              const hadValidation = ds.connectionStatus === 'tested' || ds.connectionStatus === 'error';
              const secretChanged =
                ('accessKey' in patch && patch.accessKey !== ds.accessKey) ||
                ('accessSecret' in patch && patch.accessSecret !== ds.accessSecret);
              if (hadValidation && secretChanged) {
                next.connectionStatus = 'idle';
                next.errorMessage = undefined;
              }
              return next;
            }),
          };
        }),
      }));
    },
    [],
  );

  const removeDocumentSpace = useCallback(
    (channelId: string, dsId: string) => {
      const channel = state.channels.find((c) => c.id === channelId);
      const space = channel?.documentSpaces.find((d) => d.id === dsId);
      const isPersisted = space?.connectionStatus === 'tested';

      // optimistic UI
      setState((prev) => ({
        ...prev,
        channels: prev.channels.map((ch) =>
          ch.id === channelId ? { ...ch, documentSpaces: ch.documentSpaces.filter((ds) => ds.id !== dsId) } : ch,
        ),
      }));

      if (!isPersisted) return;

      deleteDocumentMutation.mutate(dsId, {
        onError: (error) => {
          const { message } = parseChannelTalkError(error);
          toast.error('도큐먼트 스페이스 삭제에 실패했어요.', { description: message });
        },
      });
    },
    [state.channels, deleteDocumentMutation],
  );

  const testChannelConnection = useCallback(
    (channelId: string) => {
      const channel = state.channels.find((c) => c.id === channelId);
      if (!channel) return;

      // 클라이언트 단 사전 검증 — 빈 필드면 백엔드 호출 없이 즉시 에러
      if (!isChannelSecretsFilled(channel)) {
        setState((prev) => ({
          ...prev,
          channels: prev.channels.map((c) =>
            c.id === channelId
              ? {
                  ...c,
                  connectionStatus: 'error',
                  errorMessage: '필수 키가 입력되지 않았습니다. 모든 항목을 채워주세요.',
                }
              : c,
          ),
        }));
        return;
      }

      channelMutation.mutate(
        {
          access_key: channel.accessKey,
          access_secret: channel.accessSecret,
          webhook_token: channel.webhookToken,
        },
        {
          onSuccess: (response) => {
            const data = response.data;
            setState((prev) => ({
              ...prev,
              connected: true,
              lastSyncedAt: data.credential_last_verified_at,
              channels: prev.channels.map((c) =>
                c.id === channelId
                  ? {
                      ...c,
                      // 백엔드 발급 channel_id/name으로 교체
                      id: data.channel_id ?? c.id,
                      name: data.channel_name ?? c.name,
                      // 저장 후 키 필드 마스킹
                      accessKey: MASKED_PLACEHOLDER,
                      accessSecret: MASKED_PLACEHOLDER,
                      webhookToken: data.webhook_token_configured ? MASKED_PLACEHOLDER : '',
                      connectionStatus: 'tested',
                      errorMessage: undefined,
                    }
                  : c,
              ),
            }));
          },
          onError: (error) => {
            const { message } = parseChannelTalkError(error);
            setState((prev) => ({
              ...prev,
              channels: prev.channels.map((c) =>
                c.id === channelId
                  ? {
                      ...c,
                      connectionStatus: 'error',
                      errorMessage: message,
                    }
                  : c,
              ),
            }));
          },
        },
      );
    },
    [state.channels, channelMutation],
  );

  const testDocumentSpaceConnection = useCallback(
    (channelId: string, dsId: string) => {
      const channel = state.channels.find((c) => c.id === channelId);
      const ds = channel?.documentSpaces.find((d) => d.id === dsId);
      if (!ds) return;

      if (!isDocumentSpaceSecretsFilled(ds)) {
        setState((prev) => ({
          ...prev,
          channels: prev.channels.map((c) =>
            c.id !== channelId
              ? c
              : {
                  ...c,
                  documentSpaces: c.documentSpaces.map((d) =>
                    d.id === dsId
                      ? {
                          ...d,
                          connectionStatus: 'error',
                          errorMessage: '필수 키가 입력되지 않았습니다. 모든 항목을 채워주세요.',
                        }
                      : d,
                  ),
                },
          ),
        }));
        return;
      }

      documentMutation.mutate(
        {
          access_key: ds.accessKey,
          access_secret: ds.accessSecret,
        },
        {
          onSuccess: (response) => {
            const data = response.data;
            setState((prev) => ({
              ...prev,
              channels: prev.channels.map((c) =>
                c.id !== channelId
                  ? c
                  : {
                      ...c,
                      documentSpaces: c.documentSpaces.map((d) =>
                        d.id === dsId
                          ? {
                              ...d,
                              id: data.space_id ?? d.id,
                              name: data.space_name ?? d.name,
                              accessKey: MASKED_PLACEHOLDER,
                              accessSecret: MASKED_PLACEHOLDER,
                              connectionStatus: 'tested',
                              errorMessage: undefined,
                            }
                          : d,
                      ),
                    },
              ),
            }));
          },
          onError: (error) => {
            const { message } = parseChannelTalkError(error);
            setState((prev) => ({
              ...prev,
              channels: prev.channels.map((c) =>
                c.id !== channelId
                  ? c
                  : {
                      ...c,
                      documentSpaces: c.documentSpaces.map((d) =>
                        d.id === dsId ? { ...d, connectionStatus: 'error', errorMessage: message } : d,
                      ),
                    },
              ),
            }));
          },
        },
      );
    },
    [state.channels, documentMutation],
  );

  const enterDocumentSpaceEditMode = useCallback((channelId: string, dsId: string) => {
    setState((prev) => ({
      ...prev,
      channels: prev.channels.map((ch) =>
        ch.id !== channelId
          ? ch
          : {
              ...ch,
              documentSpaces: ch.documentSpaces.map((ds) =>
                ds.id === dsId
                  ? {
                      ...ds,
                      accessKey: '',
                      accessSecret: '',
                      connectionStatus: 'editing' as const,
                      errorMessage: undefined,
                    }
                  : ds,
              ),
            },
      ),
    }));
  }, []);

  return {
    state,
    addChannel,
    updateChannel,
    removeChannel,
    enterEditMode,
    addDocumentSpace,
    updateDocumentSpace,
    removeDocumentSpace,
    testChannelConnection,
    testDocumentSpaceConnection,
    enterDocumentSpaceEditMode,
  };
}
