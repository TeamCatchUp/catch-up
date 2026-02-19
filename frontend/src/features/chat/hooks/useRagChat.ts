'use client';

import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { useInitialQueryBootstrap } from '@/features/chat/hooks/useRagChat.parts/initialQueryBootstrap';
import { useMessageActions } from '@/features/chat/hooks/useRagChat.parts/messageActions';
import { refreshRecentChats } from '@/features/chat/hooks/useRagChat.parts/refreshRecentChats';
import { useRagChatRefs } from '@/features/chat/hooks/useRagChat.parts/refs';
import {
  createEmptyChatData,
  loadSessionChatData,
} from '@/features/chat/hooks/useRagChat.parts/sessionDataLoader';
import { useSessionLifecycle } from '@/features/chat/hooks/useRagChat.parts/sessionLifecycle';
import { useStreamProcessing } from '@/features/chat/hooks/useRagChat.parts/streamProcessing';
import type { UseRagChatOptions, UseRagChatReturn } from '@/features/chat/hooks/useRagChat.parts/types';
import { useRagStream } from '@/features/chat/hooks/useRagStream';
import type { ChatData, RagUIStepKey } from '@/features/chat/types';
import { isValidSessionId } from '@/shared/utils/sessionId';

/**
 * useRagChat (orchestrator)
 *
 * 이 파일의 역할:
 * - 직접 비즈니스 로직을 많이 수행하지 않고, part 훅들을 조합해서
 *   "채팅 수명주기 전체"를 하나의 API로 노출한다.
 *
 * 실행 흐름(큰 순서):
 * 1) refs/state 준비
 * 2) session lifecycle (hydrate/replace/q 정리) 연결
 * 3) stream processing (status/token/result 반영) 연결
 * 4) user actions (send/edit/stop/feedback) 연결
 * 5) initial q bootstrap (첫 질문 자동 실행 1회) 연결
 */
export const useRagChat = ({ sessionId, repo, initialQuery }: UseRagChatOptions): UseRagChatReturn => {
  // ---------------------------------------------------------------------------
  // External hooks/services
  // ---------------------------------------------------------------------------
  const router = useRouter();
  const queryClient = useQueryClient();
  const { streamChat, abortStream, markStopped, resetStopped, isStopped } = useRagStream();

  // ---------------------------------------------------------------------------
  // Derived inputs from route/query
  // ---------------------------------------------------------------------------
  const isPlaceholderSession = sessionId === 'new';

  // URL로 전달된 첫 질문(q). 빈 문자열은 null 처리한다.
  const initialQueryFromUrl = initialQuery?.trim() ? initialQuery.trim() : null;
  const effectiveInitialQuery = initialQueryFromUrl;

  // placeholder 세션(`/chat/new`)일 때만 provisional -> resolved로 확정된다.
  const [provisionalSessionId, setProvisionalSessionId] = useState<string | undefined>();
  const resolvedSessionId = isPlaceholderSession ? provisionalSessionId : sessionId;

  // ---------------------------------------------------------------------------
  // UI states exposed to page/components
  // ---------------------------------------------------------------------------
  // 화면 렌더링에 직접 사용되는 핵심 state
  const [chatData, setChatData] = useState<ChatData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(isValidSessionId(sessionId));
  const [isError, setIsError] = useState(false);
  const [currentStep, setCurrentStep] = useState<RagUIStepKey>('router');

  // 모든 ref 기반 런타임 상태(세션 전환 가드, 스트림 플래그)를 전담 훅에서 관리
  const { sessionRefs, streamRefs, resetStreamStateRefs } = useRagChatRefs(resolvedSessionId);

  const refreshRecentChatsNow = useCallback(() => {
    refreshRecentChats(queryClient);
  }, [queryClient]);

  // 비어 있는 ChatData를 만드는 helper (신규 세션/에러 fallback에서 사용)
  const buildEmptyChatData = useCallback(
    (targetSessionId: string) => createEmptyChatData(targetSessionId, repo, effectiveInitialQuery),
    [effectiveInitialQuery, repo],
  );

  // sessionDataLoader에 현재 컨텍스트(repo/initialQuery/queryClient)를 주입한 래퍼
  const loadSessionChatDataWithContext = useCallback(
    (targetSessionId: string) =>
      loadSessionChatData({
        queryClient,
        sessionId: targetSessionId,
        repo,
        initialQuery: effectiveInitialQuery,
      }),
    [effectiveInitialQuery, queryClient, repo],
  );

  // 스트림 종료 후 서버 기준 최종 메시지로 1회 동기화
  const syncChatDataFromServer = useCallback(
    async (targetSessionId: string) => {
      if (!isValidSessionId(targetSessionId)) return;
      try {
        const nextData = await loadSessionChatDataWithContext(targetSessionId);
        setChatData(nextData);
      } catch (err) {
        console.error('[useRagChat] syncChatDataFromServer error:', err);
      }
    },
    [loadSessionChatDataWithContext],
  );

  // ---------------------------------------------------------------------------
  // Part hooks composition
  // ---------------------------------------------------------------------------
  // 세션 전환 hydrate, placeholder replace, q 파라미터 정리 책임
  const { resolveSessionIdFromStream, clearInitialQueryParam } = useSessionLifecycle({
    sessionId,
    isPlaceholderSession,
    isLoading,
    chatData,
    provisionalSessionId,
    setProvisionalSessionId,
    resolvedSessionId,
    initialQueryFromUrl,
    effectiveInitialQuery,
    queryClient,
    router,
    abortStream,
    resetStreamStateRefs,
    buildEmptyChatData,
    loadSessionChatDataWithContext,
    stateSetters: {
      setChatData,
      setIsLoading,
      setIsError,
      setCurrentStep,
    },
    sessionRefs,
    streamRefs,
  });

  // SSE 이벤트(status/token/result/sources) -> UI 상태 반영 책임
  const {
    beginAnswerLoading,
    ensureInitialUserMessage,
    handleAbortError,
    appendAssistantAnswer,
    finalizeAfterStreamClose,
    handleStreamEvent,
  } = useStreamProcessing({
    effectiveInitialQuery,
    resetStopped,
    isStopped,
    resetStreamStateRefs,
    syncChatDataFromServer,
    refreshRecentChatsNow,
    resolveSessionIdFromStream,
    stateSetters: {
      setChatData,
      setIsLoading,
      setIsError,
      setCurrentStep,
    },
    sessionRefs,
    streamRefs,
  });

  // 사용자 액션(send/edit/stop/feedback) 책임
  const { sendMessage, submitEdit, handleStop, updateMessageFeedback } = useMessageActions({
    chatData,
    isLoading,
    resolvedSessionId,
    streamChat,
    handleStreamEvent,
    finalizeAfterStreamClose,
    handleAbortError,
    beginAnswerLoading,
    appendAssistantAnswer,
    refreshRecentChatsNow,
    abortStream,
    markStopped,
    setChatData,
    setIsLoading,
    setIsError,
    setCurrentStep,
    streamRefs,
  });

  // 첫 진입 시 ?q 부트스트랩(질문 1회 자동 실행) 책임
  useInitialQueryBootstrap({
    effectiveInitialQuery,
    chatData,
    isLoading,
    resolvedSessionId,
    streamChat,
    handleStreamEvent,
    finalizeAfterStreamClose,
    handleAbortError,
    beginAnswerLoading,
    clearInitialQueryParam,
    ensureInitialUserMessage,
    setIsError,
    setIsLoading,
    streamRefs,
  });

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------
  return {
    // 화면 데이터
    chatData,
    resolvedSessionId,
    isLoading,
    isError,
    currentStep,

    // 사용자 액션
    sendMessage,
    submitEdit,
    handleStop,

    // 외부 연동(필요 시 강제 업데이트)
    setChatData,
    updateMessageFeedback,
  };
};

export default useRagChat;
