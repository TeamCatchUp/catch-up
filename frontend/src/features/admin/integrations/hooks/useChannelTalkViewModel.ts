'use client';

import { useCallback, useState } from 'react';

import {
  CHANNEL_SYNC_INTERVAL_DEFAULT,
  DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
} from '../types/channelTalkModel';
import type {
  ChannelTalkChannel,
  ChannelTalkConnectionState,
  ChannelTalkDocumentSpace,
} from '../types/channelTalkModel';

/** 인터랙티브 mock 초기 상태 — 빈 채널, 새로고침 시 초기화 */
const INITIAL_STATE: ChannelTalkConnectionState = {
  connected: false,
  lastSyncedAt: null,
  channels: [],
};

/**
 * 새 ID 생성 — 단순한 mock용 timestamp + random suffix.
 * TODO(channel-talk-api): API 도입 시 백엔드가 발급하는 ID 사용.
 */
function makeId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/** 모든 secret 필드가 채워졌는지 검증 (mock validation) */
function isAllSecretsFilled(channel: ChannelTalkChannel): boolean {
  return Boolean(channel.accessKey && channel.accessSecret && channel.webhookToken);
}

interface ChannelTalkViewModel {
  state: ChannelTalkConnectionState;
  addChannel: () => void;
  updateChannel: (channelId: string, patch: Partial<ChannelTalkChannel>) => void;
  removeChannel: (channelId: string) => void;
  addDocumentSpace: (channelId: string) => void;
  updateDocumentSpace: (channelId: string, dsId: string, patch: Partial<ChannelTalkDocumentSpace>) => void;
  removeDocumentSpace: (channelId: string, dsId: string) => void;
  testChannelConnection: (channelId: string) => void;
}

/**
 * 채널톡 연동 인터랙티브 뷰모델 — useState 기반 in-memory mock.
 *
 * **현재**: 빈 초기 상태에서 시작, 사용자가 채널/도큐먼트 스페이스를 직접 추가/입력. 새로고침 시 초기화.
 * **향후 (channel-talk-api PR)**: useState → useQuery + useMutation으로 교체. 컴포넌트는 viewModel 인터페이스만 의존하므로 변경 불필요.
 */
export function useChannelTalkViewModel(): ChannelTalkViewModel {
  const [state, setState] = useState<ChannelTalkConnectionState>(INITIAL_STATE);

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

  const updateChannel = useCallback((channelId: string, patch: Partial<ChannelTalkChannel>) => {
    setState((prev) => ({
      ...prev,
      channels: prev.channels.map((ch) => {
        if (ch.id !== channelId) return ch;
        const next = { ...ch, ...patch };

        // 검증 완료(tested) / 실패(error) 후 secret 값 수정 시 → idle로 자동 복귀
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

  const removeChannel = useCallback((channelId: string) => {
    setState((prev) => ({
      ...prev,
      channels: prev.channels.filter((ch) => ch.id !== channelId),
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
                },
              ],
            }
          : ch,
      ),
    }));
  }, []);

  const updateDocumentSpace = useCallback(
    (channelId: string, dsId: string, patch: Partial<ChannelTalkDocumentSpace>) => {
      setState((prev) => ({
        ...prev,
        channels: prev.channels.map((ch) =>
          ch.id === channelId
            ? {
                ...ch,
                documentSpaces: ch.documentSpaces.map((ds) => (ds.id === dsId ? { ...ds, ...patch } : ds)),
              }
            : ch,
        ),
      }));
    },
    [],
  );

  const removeDocumentSpace = useCallback((channelId: string, dsId: string) => {
    setState((prev) => ({
      ...prev,
      channels: prev.channels.map((ch) =>
        ch.id === channelId ? { ...ch, documentSpaces: ch.documentSpaces.filter((ds) => ds.id !== dsId) } : ch,
      ),
    }));
  }, []);

  const testChannelConnection = useCallback((channelId: string) => {
    setState((prev) => ({
      ...prev,
      channels: prev.channels.map((ch) => {
        if (ch.id !== channelId) return ch;
        const allFilled = isAllSecretsFilled(ch);
        return {
          ...ch,
          connectionStatus: allFilled ? 'tested' : 'error',
          errorMessage: allFilled ? undefined : '필수 키가 입력되지 않았습니다. 모든 항목을 채워주세요.',
        };
      }),
    }));
  }, []);

  return {
    state,
    addChannel,
    updateChannel,
    removeChannel,
    addDocumentSpace,
    updateDocumentSpace,
    removeDocumentSpace,
    testChannelConnection,
  };
}
