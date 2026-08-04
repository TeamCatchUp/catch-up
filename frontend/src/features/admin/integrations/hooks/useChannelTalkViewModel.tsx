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
import { CHANNEL_TALK_SYNC_INTERVAL_HOURS } from '../types/channelTalkModel';
import {
  appendNewChannel,
  appendNewDocumentSpace,
  applyChannelPatch,
  applyChannelTestSuccess,
  applyDocumentSpacePatch,
  applyDocumentSpaceTestSuccess,
  markChannelError,
  markDocumentSpaceError,
  removeChannelById,
  removeDocumentSpaceById,
  restoreChannelAt,
  restoreDocumentSpaceAt,
} from '../utils/channelTalkConnectionState';
import { isChannelSecretsFilled, isDocumentSpaceSecretsFilled } from '../utils/channelTalkHelpers';

const MISSING_SECRETS_MESSAGE = '필수 키가 입력되지 않았습니다. 모든 항목을 채워주세요.';

/** 연결 테스트 실패 토스트 — 키 불일치는 전용 카피, 그 외는 generic. 채널·도큐먼트 공용 */
function toastCredentialError(code: string | undefined, message: string | undefined) {
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
// 상태 전이 규칙은 전부 `utils/channelTalkConnectionState.ts`의 순수 함수가 정한다
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

  const addChannel = useCallback(() => setState(appendNewChannel), []);

  const updateChannel = useCallback((channelId: string, patch: ChannelTalkChannelPatch) => {
    setState((prev) => applyChannelPatch(prev, channelId, patch));
  }, []);

  const addDocumentSpace = useCallback((channelId: string) => {
    setState((prev) => appendNewDocumentSpace(prev, channelId));
  }, []);

  const updateDocumentSpace = useCallback((channelId: string, dsId: string, patch: ChannelTalkDocumentSpacePatch) => {
    setState((prev) => applyDocumentSpacePatch(prev, channelId, dsId, patch));
  }, []);

  const removeChannel = useCallback(
    (channelId: string) => {
      // stateRef로 latest state 읽기 — closure 의존성 제거로 callback identity stable.
      const removedIndex = stateRef.current.channels.findIndex((c) => c.id === channelId);
      if (removedIndex < 0) return;
      const snapshot = stateRef.current.channels[removedIndex];

      setState((prev) => removeChannelById(prev, channelId));

      // 검증 통과한 채널만 백엔드에 등록되어 있으므로 DELETE 호출 대상.
      if (snapshot.connectionStatus !== 'tested') return;

      deleteChannelMutation.mutate(channelId, {
        onError: (error) => {
          setState((prev) => restoreChannelAt(prev, snapshot, removedIndex));
          const { message } = parseApiError(error);
          toast('채널 삭제에 실패했어요.', { description: message });
        },
      });
    },
    [deleteChannelMutation],
  );

  const removeDocumentSpace = useCallback(
    (channelId: string, dsId: string) => {
      const targetChannel = stateRef.current.channels.find((c) => c.id === channelId);
      if (!targetChannel) return;
      const removedIndex = targetChannel.documentSpaces.findIndex((d) => d.id === dsId);
      if (removedIndex < 0) return;
      const snapshot = targetChannel.documentSpaces[removedIndex];

      setState((prev) => removeDocumentSpaceById(prev, channelId, dsId));

      if (snapshot.connectionStatus !== 'tested') return;

      deleteDocumentMutation.mutate(dsId, {
        onError: (error) => {
          setState((prev) => restoreDocumentSpaceAt(prev, channelId, snapshot, removedIndex));
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
        setState((prev) => markChannelError(prev, channelId, MISSING_SECRETS_MESSAGE));
        return;
      }

      setPendingChannelIds((prev) => new Set(prev).add(channelId));

      channelMutation.mutate(
        {
          access_key: channel.accessKey,
          access_secret: channel.accessSecret,
          webhook_token: channel.webhookToken,
        },
        {
          onSuccess: (response) => {
            setState((prev) => applyChannelTestSuccess(prev, channelId, response.data));
            toast('연결에 성공했어요.', { description: '이제 동기화를 시작할 수 있어요.' });
          },
          onError: (error) => {
            const { code, message } = parseApiError(error);
            setState((prev) => markChannelError(prev, channelId));
            toastCredentialError(code, message);
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
        setState((prev) => markDocumentSpaceError(prev, channelId, dsId, MISSING_SECRETS_MESSAGE));
        return;
      }

      setPendingDocumentSpaceIds((prev) => new Set(prev).add(dsId));

      documentMutation.mutate(
        {
          access_key: ds.accessKey,
          access_secret: ds.accessSecret,
          polling_cycle_hours: CHANNEL_TALK_SYNC_INTERVAL_HOURS[ds.syncInterval],
        },
        {
          onSuccess: (response) => {
            setState((prev) => applyDocumentSpaceTestSuccess(prev, channelId, dsId, response.data));
            toast('연결에 성공했어요.', { description: '이제 동기화를 시작할 수 있어요.' });
          },
          onError: (error) => {
            const { code, message } = parseApiError(error);
            setState((prev) => markDocumentSpaceError(prev, channelId, dsId));
            toastCredentialError(code, message);
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
