import type { Dispatch, SetStateAction } from 'react';
import { useCallback } from 'react';

import chatService from '@/features/chat/services/chatService';
import { ChatStreamHttpError } from '@/features/chat/services/realChatService';
import type {
  ChatData,
  PipelineQueryType,
  SseRenderMode,
  SseStreamEventEnvelopeApi,
  StepRow,
  StreamEvent,
} from '@/features/chat/types';
import { applyReconnectStreamWithCutoff } from '@/features/chat/utils/stream/buildReconnectStreamHandler';

import type { StreamRuntimeRefs } from './types';

interface UseMessageActionsParams {
  // 현재 UI 상태
  chatData: ChatData | null;
  isLoading: boolean;
  resolvedSessionId: string | undefined;

  // 스트림 실행/후처리
  streamChat: (query: string, sessionId: string | undefined, onEvent: (event: StreamEvent) => void) => Promise<void>;
  handleStreamEvent: (event: StreamEvent) => void;
  handleStreamEvents: (events: readonly StreamEvent[], options?: { renderMode?: SseRenderMode }) => void;
  finalizeAfterStreamClose: () => Promise<void>;
  handleAbortError: () => void;
  beginAnswerLoading: () => void;
  appendAssistantAnswer: (answer?: string) => void;

  // 부수효과/외부 제어
  cancelGeneration: (sessionId: string) => Promise<void>;
  reconnectChatStream: (sessionId: string, onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void) => Promise<void>;
  abortStream: () => void;
  markStopped: () => void;
  setChatData: Dispatch<SetStateAction<ChatData | null>>;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  setIsError: Dispatch<SetStateAction<boolean>>;
  setStepRows: Dispatch<SetStateAction<StepRow[]>>;
  setPipelineQueryType: Dispatch<SetStateAction<PipelineQueryType | null>>;
  setTopic: Dispatch<SetStateAction<string | null>>;
  setPipelineReasoning: Dispatch<SetStateAction<string | null>>;
  streamRefs: StreamRuntimeRefs;
}

interface UseMessageActionsReturn {
  sendMessage: (message: string) => Promise<void>;
  submitEdit: (messageId: string, newContent: string) => Promise<void>;
  handleStop: () => void;
  updateMessageFeedback: (messageId: string, isLiked: boolean | undefined) => void;
}

/**
 * 사용자 액션(send/edit/stop/feedback) 관련 콜백 묶음.
 */
export const useMessageActions = ({
  chatData,
  isLoading,
  resolvedSessionId,
  streamChat,
  handleStreamEvent,
  handleStreamEvents,
  finalizeAfterStreamClose,
  handleAbortError,
  beginAnswerLoading,
  appendAssistantAnswer,
  cancelGeneration,
  reconnectChatStream,
  abortStream,
  markStopped,
  setChatData,
  setIsLoading,
  setIsError,
  setStepRows,
  setPipelineQueryType,
  setTopic,
  setPipelineReasoning,
  streamRefs,
}: UseMessageActionsParams): UseMessageActionsReturn => {
  // ---------------------------------------------------------------------------
  // Shared refs
  // ---------------------------------------------------------------------------
  const { activeQuestionRef, streamInFlightRef, streamingMessageIdRef } = streamRefs;

  const isAbortError = useCallback(
    (err: unknown): boolean =>
      err instanceof DOMException ? err.name === 'AbortError' : err instanceof Error && err.name === 'AbortError',
    [],
  );

  const reconnectActiveStream = useCallback(
    async (chatDataSnapshot: ChatData | null): Promise<boolean> => {
      if (!resolvedSessionId) return false;

      setChatData(chatDataSnapshot);
      streamInFlightRef.current = true;

      try {
        const status = await chatService.getGenerationStatus(resolvedSessionId);
        if (!status.is_generating) return false;

        await applyReconnectStreamWithCutoff({
          sessionId: resolvedSessionId,
          cutoffId: status.cutoff_id,
          reconnectChatStream,
          handleStreamEvents,
        });
        await finalizeAfterStreamClose();
        return true;
      } catch (err) {
        if (isAbortError(err)) {
          handleAbortError();
          return true;
        }
        throw err;
      }
    },
    [
      finalizeAfterStreamClose,
      handleAbortError,
      handleStreamEvents,
      isAbortError,
      reconnectChatStream,
      resolvedSessionId,
      setChatData,
      streamInFlightRef,
    ],
  );

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------
  /**
   * 일반 질문 전송
   * 1) user 메시지 즉시 append (낙관적 UI)
   * 2) 스트림 시작
   * 3) 종료 후 finalize 동기화
   */
  const sendMessage = useCallback(
    async (message: string) => {
      // 중복 요청/빈 입력 방지
      if (!message.trim() || isLoading || !chatData || streamInFlightRef.current) return;

      const createdAt = new Date().toISOString();
      const updated: ChatData = {
        ...chatData,
        messages: [
          ...chatData.messages,
          {
            id: crypto.randomUUID(),
            role: 'user',
            content: message,
            timestamp: createdAt,
          },
        ],
      };
      setChatData(updated);
      activeQuestionRef.current = { content: message, createdAt, tempId: -Date.now() };

      beginAnswerLoading();

      try {
        await streamChat(message, resolvedSessionId, handleStreamEvent);
        await finalizeAfterStreamClose();
      } catch (err) {
        let errorToHandle = err;

        if (err instanceof ChatStreamHttpError && err.status === 409) {
          try {
            if (await reconnectActiveStream(chatData)) {
              activeQuestionRef.current = null;
              return;
            }
          } catch (reconnectErr) {
            errorToHandle = reconnectErr;
          }
        }

        if (isAbortError(errorToHandle)) {
          handleAbortError();
          return;
        }
        console.error('[useRagChat] sendMessage error:', errorToHandle);
        setIsError(true);
        setIsLoading(false);
        activeQuestionRef.current = null;
        streamInFlightRef.current = false;
      }
    },
    [
      activeQuestionRef,
      beginAnswerLoading,
      chatData,
      finalizeAfterStreamClose,
      handleAbortError,
      handleStreamEvent,
      isLoading,
      isAbortError,
      reconnectActiveStream,
      resolvedSessionId,
      setChatData,
      setIsError,
      setIsLoading,
      streamChat,
      streamInFlightRef,
    ],
  );

  /**
   * 질문 수정 후 재질문
   * - 편집 대상 이후 대화는 버리고, 수정된 user 메시지부터 다시 스트림한다.
   * - 가능하면 reset-last API로 서버 마지막 턴을 soft-delete 후 재생성한다.
   */
  const submitEdit = useCallback(
    async (messageId: string, newContent: string) => {
      if (!chatData || streamInFlightRef.current) return;

      const targetIndex = chatData.messages.findIndex((message) => message.id === messageId);
      if (targetIndex === -1) return;

      const createdAt = new Date().toISOString();
      const updated: ChatData = {
        ...chatData,
        messages: [
          ...chatData.messages.slice(0, targetIndex),
          {
            id: crypto.randomUUID(),
            role: 'user',
            content: newContent,
            timestamp: createdAt,
          },
        ],
      };
      setChatData(updated);
      activeQuestionRef.current = { content: newContent, createdAt, tempId: -Date.now() };

      beginAnswerLoading();

      try {
        try {
          // reset 실패해도 사용자 흐름은 멈추지 않는다.
          if (resolvedSessionId) {
            await chatService.resetLastTurn(resolvedSessionId);
          }
        } catch (resetErr) {
          console.warn('[useRagChat] resetLastTurn failed, proceeding with stream:', resetErr);
        }

        await streamChat(newContent, resolvedSessionId, handleStreamEvent);
        await finalizeAfterStreamClose();
      } catch (err) {
        let errorToHandle = err;

        if (err instanceof ChatStreamHttpError && err.status === 409) {
          try {
            if (await reconnectActiveStream(chatData)) {
              activeQuestionRef.current = null;
              return;
            }
          } catch (reconnectErr) {
            errorToHandle = reconnectErr;
          }
        }

        if (isAbortError(errorToHandle)) {
          handleAbortError();
          return;
        }
        console.error('[useRagChat] submitEdit error:', errorToHandle);
        setIsError(true);
        setIsLoading(false);
        activeQuestionRef.current = null;
        streamInFlightRef.current = false;
      }
    },
    [
      activeQuestionRef,
      beginAnswerLoading,
      chatData,
      finalizeAfterStreamClose,
      handleAbortError,
      handleStreamEvent,
      isAbortError,
      reconnectActiveStream,
      resolvedSessionId,
      setChatData,
      setIsError,
      setIsLoading,
      streamChat,
      streamInFlightRef,
    ],
  );

  /**
   * 사용자 강제 중단(Stop 버튼)
   * - SSE abort + 로딩 해제
   * - 토큰을 하나도 못 받은 경우에는 빈 assistant 메시지를 남겨 UI 짝을 맞춘다.
   */
  const handleStop = useCallback(() => {
    if (!isLoading) return;

    markStopped();
    activeQuestionRef.current = null;
    if (resolvedSessionId) {
      void cancelGeneration(resolvedSessionId).catch((err) => {
        console.warn('[useRagChat] cancelGeneration failed:', err);
      });
    }
    abortStream();

    setIsLoading(false);
    setIsError(false);
    setStepRows([]);
    setPipelineQueryType(null);
    setTopic(null);
    setPipelineReasoning(null);

    if (!streamingMessageIdRef.current) {
      streamInFlightRef.current = false;
      appendAssistantAnswer('\n');
      return;
    }

    streamInFlightRef.current = false;
  }, [
    abortStream,
    activeQuestionRef,
    appendAssistantAnswer,
    cancelGeneration,
    isLoading,
    markStopped,
    resolvedSessionId,
    setIsError,
    setIsLoading,
    setPipelineQueryType,
    setPipelineReasoning,
    setStepRows,
    setTopic,
    streamInFlightRef,
    streamingMessageIdRef,
  ]);

  /**
   * 특정 assistant 메시지의 feedback 제출 완료 상태를 로컬에 반영
   */
  const updateMessageFeedback = useCallback(
    (messageId: string, isLiked: boolean | undefined) => {
      setChatData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: prev.messages.map((message) =>
            message.id === messageId ? { ...message, has_feedback: isLiked !== undefined, is_liked: isLiked } : message,
          ),
        };
      });
    },
    [setChatData],
  );

  return {
    sendMessage,
    submitEdit,
    handleStop,
    updateMessageFeedback,
  };
};
