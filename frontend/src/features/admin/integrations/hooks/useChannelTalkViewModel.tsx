'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { parseApiError } from '@/shared/api/errors';

import { channelTalkMutations } from '../queries/channelTalk.mutations';
import type {
  ChannelTalkChannelPatch,
  ChannelTalkConnectionState,
  ChannelTalkDocumentSpacePatch,
} from '../types/channelTalkModel';
import {
  CHANNEL_TALK_SYNC_INTERVAL_HOURS,
  DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
  MASKED_PLACEHOLDER,
} from '../types/channelTalkModel';
import { isChannelSecretsFilled, isDocumentSpaceSecretsFilled } from '../utils/channelTalkHelpers';

// 미검증 카드의 임시 client-side ID. 검증 통과 시 백엔드 channel_id/space_id로 교체
function makeId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

interface ChannelTalkViewModel {
  state: ChannelTalkConnectionState;
  addChannel: () => void;
  updateChannel: (channelId: string, patch: ChannelTalkChannelPatch) => void;
  removeChannel: (channelId: string) => void;
  addDocumentSpace: (channelId: string) => void;
  updateDocumentSpace: (channelId: string, dsId: string, patch: ChannelTalkDocumentSpacePatch) => void;
  removeDocumentSpace: (channelId: string, dsId: string) => void;
  testChannelConnection: (channelId: string) => void;
  testDocumentSpaceConnection: (channelId: string, dsId: string) => void;
}

// 채널톡 연동 viewModel. initialState는 호출자가 백엔드 GET 응답에서 derive해 전달
// 검증+저장은 "연결 테스트 하기" 버튼 클릭 시 validate→save 통합 mutation으로 실행
// 삭제는 optimistic UI — 백엔드 실패 시 원래 위치에 복원
export function useChannelTalkViewModel(initialState: ChannelTalkConnectionState): ChannelTalkViewModel {
  const [state, setState] = useState<ChannelTalkConnectionState>(initialState);
  // optimistic delete의 snapshot capture용 latest state mirror.
  // useCallback deps에서 state.channels 제거하여 callback identity stable 유지
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  // 진행 중 mutation 추적 — 동일 카드 중복 클릭 방지
  const [pendingChannelIds, setPendingChannelIds] = useState<Set<string>>(() => new Set());
  const [pendingDocumentSpaceIds, setPendingDocumentSpaceIds] = useState<Set<string>>(() => new Set());

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
      // stateRef로 latest state 읽기 — closure 의존성 제거로 callback identity stable.
      const removedIndex = stateRef.current.channels.findIndex((c) => c.id === channelId);
      if (removedIndex < 0) return;
      const snapshot = stateRef.current.channels[removedIndex];

      // optimistic UI: 즉시 화면에서 제거. 마지막 채널이면 connected=false로 동기화.
      setState((prev) => {
        const nextChannels = prev.channels.filter((ch) => ch.id !== channelId);
        return { ...prev, channels: nextChannels, connected: nextChannels.length > 0 && prev.connected };
      });

      // 검증 통과한 채널만 백엔드에 등록되어 있으므로 DELETE 호출 대상.
      if (snapshot.connectionStatus !== 'tested') return;

      deleteChannelMutation.mutate(channelId, {
        onError: (error) => {
          // 백엔드 삭제 실패 → 원래 위치에 복원하여 사용자에게 일관된 view 유지.
          setState((prev) => {
            const next = [...prev.channels];
            const insertAt = Math.min(removedIndex, next.length);
            next.splice(insertAt, 0, snapshot);
            return { ...prev, channels: next };
          });
          const { message } = parseApiError(error);
          toast('채널 삭제에 실패했어요.', { description: message });
        },
      });
    },
    [deleteChannelMutation],
  );

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

  const updateDocumentSpace = useCallback((channelId: string, dsId: string, patch: ChannelTalkDocumentSpacePatch) => {
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
  }, []);

  const removeDocumentSpace = useCallback(
    (channelId: string, dsId: string) => {
      // removeChannel과 동일 패턴 — stateRef로 latest 읽어 callback identity stable.
      const targetChannel = stateRef.current.channels.find((c) => c.id === channelId);
      if (!targetChannel) return;
      const removedIndex = targetChannel.documentSpaces.findIndex((d) => d.id === dsId);
      if (removedIndex < 0) return;
      const snapshot = targetChannel.documentSpaces[removedIndex];

      setState((prev) => ({
        ...prev,
        channels: prev.channels.map((ch) =>
          ch.id === channelId ? { ...ch, documentSpaces: ch.documentSpaces.filter((ds) => ds.id !== dsId) } : ch,
        ),
      }));

      if (snapshot.connectionStatus !== 'tested') return;

      deleteDocumentMutation.mutate(dsId, {
        onError: (error) => {
          // 원래 위치에 복원
          setState((prev) => ({
            ...prev,
            channels: prev.channels.map((ch) => {
              if (ch.id !== channelId) return ch;
              const next = [...ch.documentSpaces];
              const insertAt = Math.min(removedIndex, next.length);
              next.splice(insertAt, 0, snapshot);
              return { ...ch, documentSpaces: next };
            }),
          }));
          const { message } = parseApiError(error);
          toast('도큐먼트 스페이스 삭제에 실패했어요.', { description: message });
        },
      });
    },
    [deleteDocumentMutation],
  );

  const testChannelConnection = useCallback(
    (channelId: string) => {
      // 같은 카드의 mutation이 이미 진행 중이면 중복 호출 무시 (validate+save 2번 실행 방지)
      if (pendingChannelIds.has(channelId)) return;

      const channel = stateRef.current.channels.find((c) => c.id === channelId);
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

      setPendingChannelIds((prev) => {
        const next = new Set(prev);
        next.add(channelId);
        return next;
      });

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
            toast('연결에 성공했어요.', { description: '이제 동기화를 시작할 수 있어요.' });
          },
          onError: (error) => {
            const { code, message } = parseApiError(error);
            // raw 영문 에러가 inline에 노출되지 않도록 errorMessage 비움. 빨간 테두리 + toast로 안내
            setState((prev) => ({
              ...prev,
              channels: prev.channels.map((c) =>
                c.id === channelId
                  ? {
                      ...c,
                      connectionStatus: 'error',
                      errorMessage: undefined,
                    }
                  : c,
              ),
            }));
            // 키 불일치는 전용 toast, 그 외는 generic
            if (code === 'invalid_credentials') {
              toast(
                <>
                  Access Key 또는 Secret Key가 일치하지
                  <br />
                  않아요.
                </>,
                { description: '채널톡에서 다시 확인해주세요' },
              );
            } else {
              toast('연결 테스트에 실패했어요.', { description: message });
            }
          },
          onSettled: () => {
            setPendingChannelIds((prev) => {
              if (!prev.has(channelId)) return prev;
              const next = new Set(prev);
              next.delete(channelId);
              return next;
            });
          },
        },
      );
    },
    [pendingChannelIds, channelMutation],
  );

  const testDocumentSpaceConnection = useCallback(
    (channelId: string, dsId: string) => {
      if (pendingDocumentSpaceIds.has(dsId)) return;

      const channel = stateRef.current.channels.find((c) => c.id === channelId);
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

      setPendingDocumentSpaceIds((prev) => {
        const next = new Set(prev);
        next.add(dsId);
        return next;
      });

      documentMutation.mutate(
        {
          access_key: ds.accessKey,
          access_secret: ds.accessSecret,
          polling_cycle_hours: CHANNEL_TALK_SYNC_INTERVAL_HOURS[ds.syncInterval],
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
            toast('연결에 성공했어요.', { description: '이제 동기화를 시작할 수 있어요.' });
          },
          onError: (error) => {
            const { code, message } = parseApiError(error);
            setState((prev) => ({
              ...prev,
              channels: prev.channels.map((c) =>
                c.id !== channelId
                  ? c
                  : {
                      ...c,
                      documentSpaces: c.documentSpaces.map((d) =>
                        d.id === dsId ? { ...d, connectionStatus: 'error', errorMessage: undefined } : d,
                      ),
                    },
              ),
            }));
            if (code === 'invalid_credentials') {
              toast(
                <>
                  Access Key 또는 Secret Key가 일치하지
                  <br />
                  않아요.
                </>,
                { description: '채널톡에서 다시 확인해주세요' },
              );
            } else {
              toast('연결 테스트에 실패했어요.', { description: message });
            }
          },
          onSettled: () => {
            setPendingDocumentSpaceIds((prev) => {
              if (!prev.has(dsId)) return prev;
              const next = new Set(prev);
              next.delete(dsId);
              return next;
            });
          },
        },
      );
    },
    [pendingDocumentSpaceIds, documentMutation],
  );

  return {
    state,
    addChannel,
    updateChannel,
    removeChannel,
    addDocumentSpace,
    updateDocumentSpace,
    removeDocumentSpace,
    testChannelConnection,
    testDocumentSpaceConnection,
  };
}
