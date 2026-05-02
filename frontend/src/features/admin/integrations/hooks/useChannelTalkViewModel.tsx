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
  CHANNEL_SYNC_INTERVAL_DEFAULT,
  DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
  MASKED_PLACEHOLDER,
} from '../types/channelTalkModel';
import { isChannelSecretsFilled, isDocumentSpaceSecretsFilled } from '../utils/channelTalkHelpers';

/**
 * 사용자가 새로 추가한 미검증 카드의 임시 client-side ID.
 * 검증 통과 시 백엔드가 발급한 channel_id/space_id로 교체된다.
 */
function makeId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
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
  /**
   * latest state mirror — optimistic delete의 snapshot capture에 사용.
   * `useCallback` deps에 `state.channels`를 넣으면 매 state 변경마다 callback identity가
   * 변경돼 자식 카드의 prop reference 비교가 깨진다. ref로 latest를 읽어 callback identity를
   * stable하게 유지 (`rerender-functional-setstate` 룰 준수).
   *
   * React 19 룰(`react-hooks/refs`)에 따라 ref 업데이트는 render 중이 아닌 effect에서.
   * event handler에서 ref를 읽을 때는 항상 commit 이후라 안전.
   */
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  /** 검증 mutation 진행 중인 항목 추적 — 동일 카드 중복 클릭 방지에 사용 */
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
          toast.error('채널 삭제에 실패했어요.', { description: message });
        },
      });
    },
    [deleteChannelMutation],
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
          toast.error('도큐먼트 스페이스 삭제에 실패했어요.', { description: message });
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
            // 백엔드 mutation 실패는 카드의 errorMessage를 비워서 raw 영문(예: "Request failed with status code 500")이
            // inline에 노출되지 않도록 함. 빨간 테두리(connectionStatus: 'error')만으로도 시각 표시되고,
            // 자세한 사유는 toast로 안내.
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
            // 에러 분기: 외부 키 불일치는 Figma 스펙 toast, 그 외는 generic toast.
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
              toast.error('연결 테스트에 실패했어요.', { description: message });
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
              toast.error('연결 테스트에 실패했어요.', { description: message });
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
