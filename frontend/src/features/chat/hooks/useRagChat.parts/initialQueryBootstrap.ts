import type { Dispatch, SetStateAction } from 'react';
import { useEffect } from 'react';

import chatService from '@/features/chat/services/chatService';
import { ChatStreamHttpError } from '@/features/chat/services/realChatService';
import type { ChatData, SseRenderMode, SseStreamEventEnvelopeApi, StreamEvent } from '@/features/chat/types';
import { applyReconnectStreamWithCutoff } from '@/features/chat/utils/stream/buildReconnectStreamHandler';

import type { StreamRuntimeRefs } from './types';

interface UseInitialQueryBootstrapParams {
  // URL q에서 파생된 첫 질문
  effectiveInitialQuery: string | null;
  chatData: ChatData | null;
  isLoading: boolean;
  resolvedSessionId: string | undefined;

  // 스트림 제어
  streamChat: (query: string, sessionId: string | undefined, onEvent: (event: StreamEvent) => void) => Promise<void>;
  reconnectChatStream: (sessionId: string, onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void) => Promise<void>;
  handleStreamEvent: (event: StreamEvent) => void;
  handleStreamEvents: (events: readonly StreamEvent[], options?: { renderMode?: SseRenderMode }) => void;
  finalizeAfterStreamClose: () => Promise<void>;
  handleAbortError: () => void;
  beginAnswerLoading: () => void;

  // q 파라미터/메시지 보정
  clearInitialQueryParam: () => void;
  ensureInitialUserMessage: (query: string) => void;

  // 상태 세터 + ref
  setIsError: Dispatch<SetStateAction<boolean>>;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  streamRefs: StreamRuntimeRefs;
}

/**
 * URL의 `?q=`를 읽어서 "첫 질문 자동 실행"을 1회만 수행한다.
 */
export const useInitialQueryBootstrap = ({
  effectiveInitialQuery,
  chatData,
  isLoading,
  resolvedSessionId,
  streamChat,
  reconnectChatStream,
  handleStreamEvent,
  handleStreamEvents,
  finalizeAfterStreamClose,
  handleAbortError,
  beginAnswerLoading,
  clearInitialQueryParam,
  ensureInitialUserMessage,
  setIsError,
  setIsLoading,
  streamRefs,
}: UseInitialQueryBootstrapParams) => {
  // ---------------------------------------------------------------------------
  // Shared refs
  // ---------------------------------------------------------------------------
  const { activeQuestionRef, streamInFlightRef, hasAttemptedInitialStreamRef } = streamRefs;

  // ---------------------------------------------------------------------------
  // Bootstrap effects
  // ---------------------------------------------------------------------------
  /**
   * q가 있는데 user 메시지가 비어 있으면, 렌더 직후 1회 삽입한다.
   * (token이 먼저 도착하는 race에서도 대화 짝(user->assistant)이 보장된다.)
   */
  useEffect(() => {
    if (!effectiveInitialQuery) return;
    if (!chatData) return;

    const hasUserMessage = chatData.messages.some((message) => message.role === 'user');
    if (hasUserMessage) return;

    queueMicrotask(() => {
      ensureInitialUserMessage(effectiveInitialQuery);
    });
  }, [chatData, effectiveInitialQuery, ensureInitialUserMessage]);

  /**
   * q 기반 자동 스트림을 1회만 실행한다.
   *
   * 분기:
   * - assistant가 이미 있으면: 재실행하지 않고 q만 제거
   * - assistant가 없으면: stream 실행 후 finalize
   */
  useEffect(() => {
    if (!effectiveInitialQuery) return;
    if (!chatData) return;
    if (isLoading) return;
    if (streamInFlightRef.current) return;
    if (hasAttemptedInitialStreamRef.current) return;

    const hasAssistantContent = chatData.messages.some(
      (message) => message.role === 'assistant' && Boolean(message.content?.trim()),
    );
    if (hasAssistantContent) {
      // 히스토리 재진입 케이스: 자동 스트림 금지 + q 정리
      hasAttemptedInitialStreamRef.current = true;
      clearInitialQueryParam();
      return;
    }

    const runStream = async () => {
      // 자동 스트림 시작 전에 q를 제거해 effect 재진입 루프를 막는다.
      const createdAt = new Date().toISOString();
      activeQuestionRef.current = { content: effectiveInitialQuery, createdAt, tempId: -Date.now() };
      ensureInitialUserMessage(effectiveInitialQuery);
      hasAttemptedInitialStreamRef.current = true;
      clearInitialQueryParam();
      beginAnswerLoading();

      try {
        await streamChat(effectiveInitialQuery, resolvedSessionId, handleStreamEvent);
        await finalizeAfterStreamClose();
      } catch (err) {
        if (err instanceof ChatStreamHttpError && err.status === 409 && resolvedSessionId) {
          try {
            const status = await chatService.getGenerationStatus(resolvedSessionId);
            if (status.is_generating) {
              await applyReconnectStreamWithCutoff({
                sessionId: resolvedSessionId,
                cutoffId: status.cutoff_id,
                reconnectChatStream,
                handleStreamEvents,
              });
              await finalizeAfterStreamClose();
              return;
            }
          } catch (reconnectErr) {
            err = reconnectErr;
          }
        }

        if ((err as Error).name === 'AbortError') {
          handleAbortError();
          return;
        }
        console.error('[useRagChat] fetchFirstAnswer error:', err);
        setIsError(true);
        setIsLoading(false);
        activeQuestionRef.current = null;
        streamInFlightRef.current = false;
      }
    };

    void runStream();
  }, [
    activeQuestionRef,
    beginAnswerLoading,
    chatData,
    clearInitialQueryParam,
    effectiveInitialQuery,
    ensureInitialUserMessage,
    finalizeAfterStreamClose,
    handleAbortError,
    handleStreamEvent,
    handleStreamEvents,
    hasAttemptedInitialStreamRef,
    isLoading,
    reconnectChatStream,
    resolvedSessionId,
    setIsError,
    setIsLoading,
    streamChat,
    streamInFlightRef,
  ]);
};
