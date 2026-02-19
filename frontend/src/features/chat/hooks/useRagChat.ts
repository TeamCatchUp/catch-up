'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { getStorageKeys, NODE_TO_UI_STEP } from '@/features/chat/constants/config';
import { buildInitialChatData, loadSavedChat } from '@/features/chat/hooks/useRagChat.parts/chatStorage';
import {
  clearPendingInitialQuery,
  getEffectiveInitialQuery,
} from '@/features/chat/hooks/useRagChat.parts/pendingQuery';
import { refreshRecentChats } from '@/features/chat/hooks/useRagChat.parts/refreshRecentChats';
import {
  appendStreamingToken,
  updateStreamingSources,
} from '@/features/chat/hooks/useRagChat.parts/streamMessageUpdater';
import { useRagStream } from '@/features/chat/hooks/useRagStream';
import chatService from '@/features/chat/services/chatService';
import type {
  ChatData,
  ChatSource,
  Message,
  RagUIStepKey,
  SourceResponse,
  StreamEvent,
} from '@/features/chat/types';
import { normalizeSources } from '@/features/chat/utils/normalize/normalizeRagSources';
import { normalizeRelatedJiraIssues } from '@/features/chat/utils/normalize/normalizeRelatedJiraIssues';
import { setToLocalStorage } from '@/shared/hooks/useLocalStorage';

/**
 * RAG 채팅 훅 옵션
 */
interface UseRagChatOptions {
  sessionId: string;
  repo: string | null;
  initialQuery: string | null;
}

/**
 * RAG 채팅 훅 반환 타입
 */
interface UseRagChatReturn {
  chatData: ChatData | null;
  isLoading: boolean;
  isError: boolean;
  currentStep: RagUIStepKey;
  sendMessage: (message: string) => Promise<void>;
  submitEdit: (messageId: string, newContent: string) => Promise<void>;
  handleStop: () => void;
  setChatData: React.Dispatch<React.SetStateAction<ChatData | null>>;
  updateMessageFeedback: (messageId: string) => void;
}

/**
 * RAG 채팅 통합 관리 훅
 *
 * 채팅 세션의 전체 lifecycle을 관리하는 중앙 훅
 * - SSE 스트림 연결 및 이벤트 처리
 * - 메시지 상태 관리 (user/assistant)
 * - localStorage 기반 세션 영속화
 * - 스트림 중단 및 재개
 */
export const useRagChat = ({ sessionId, repo, initialQuery }: UseRagChatOptions): UseRagChatReturn => {
  const storageKeys = getStorageKeys(sessionId);
  const effectiveInitialQuery = getEffectiveInitialQuery(initialQuery, sessionId);
  const { streamChat, abortStream, markStopped, resetStopped, isStopped } = useRagStream(sessionId);
  const queryClient = useQueryClient();

  const [chatData, setChatData] = useState<ChatData | null>(() =>
    buildInitialChatData(sessionId, repo, effectiveInitialQuery, storageKeys.chat),
  );
  const [isLoading, setIsLoading] = useState<boolean>(
    () => !loadSavedChat(storageKeys.chat) && !!effectiveInitialQuery,
  );
  const [isError, setIsError] = useState(false);
  const [currentStep, setCurrentStep] = useState<RagUIStepKey>('router');
  const syncedSessionRef = useRef(sessionId);

  const refreshRecentChatsNow = useCallback(() => {
    refreshRecentChats(queryClient);
  }, [queryClient]);

  /**
   * 스트림 진행 상태 추적 ref들
   */
  const streamingMessageIdRef = useRef<string | null>(null);
  const hasStreamedTokenRef = useRef(false);
  const hasResultEventRef = useRef(false);
  const latestSourcesRef = useRef<SourceResponse[]>([]);
  const latestUiSourcesRef = useRef<ChatSource[]>([]);
  const streamInFlightRef = useRef(false);

  const resetStreamStateRefs = useCallback(() => {
    streamingMessageIdRef.current = null;
    hasStreamedTokenRef.current = false;
    hasResultEventRef.current = false;
    latestSourcesRef.current = [];
    latestUiSourcesRef.current = [];
  }, []);

  useEffect(() => {
    if (syncedSessionRef.current === sessionId) return;
    syncedSessionRef.current = sessionId;

    streamInFlightRef.current = false;
    resetStreamStateRefs();
    abortStream();

    const nextData = buildInitialChatData(sessionId, repo, effectiveInitialQuery, storageKeys.chat);
    const hasSaved = !!loadSavedChat(storageKeys.chat);
    queueMicrotask(() => {
      setIsError(false);
      setCurrentStep('router');
      setChatData(nextData);
      setIsLoading(!hasSaved && !!effectiveInitialQuery);
    });
  }, [abortStream, effectiveInitialQuery, repo, resetStreamStateRefs, sessionId, storageKeys.chat]);

  const beginAnswerLoading = useCallback(() => {
    resetStopped();
    resetStreamStateRefs();
    streamInFlightRef.current = true;
    setIsLoading(true);
    setIsError(false);
    setCurrentStep('router');
  }, [resetStopped, resetStreamStateRefs]);

  const ensureInitialUserMessage = useCallback(
    (query: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;

      setChatData((prev) => {
        if (!prev) return prev;

        const hasUser = prev.messages.some((message) => message.role === 'user');
        if (hasUser) return prev;

        const userMessage: Message = {
          id: crypto.randomUUID(),
          role: 'user',
          content: trimmed,
          timestamp: new Date().toISOString(),
        };

        const nextData: ChatData = {
          ...prev,
          title: prev.title || trimmed,
          messages: [...prev.messages, userMessage],
        };

        setToLocalStorage(storageKeys.chat, nextData);
        return nextData;
      });
    },
    [storageKeys.chat],
  );

  const handleAbortError = useCallback(() => {
    streamInFlightRef.current = false;

    if (isStopped()) return;

    setIsLoading(false);
    setCurrentStep('router');
  }, [isStopped]);

  const appendAssistantAnswer = useCallback(
    (
      answer = '',
      sources: SourceResponse[] = [],
      relatedJiraIssues: SourceResponse[] = [],
      chatHistoryId?: string,
      hasFeedback?: boolean,
    ) => {
      setChatData((prev) => {
        if (!prev) return prev;

        const uiSources = normalizeSources(sources);
        const detailedTasks = normalizeRelatedJiraIssues(relatedJiraIssues);
        latestSourcesRef.current = sources;
        latestUiSourcesRef.current = uiSources;

        if (streamingMessageIdRef.current) {
          const streamMessageIndex = prev.messages.findIndex((message) => message.id === streamingMessageIdRef.current);
          if (streamMessageIndex >= 0) {
            const messages = [...prev.messages];
            const currentMessage = messages[streamMessageIndex];

            messages[streamMessageIndex] = {
              ...currentMessage,
              content: answer || currentMessage.content,
              sources: uiSources.length ? uiSources : (currentMessage.sources ?? []),
              detailed_tasks: detailedTasks,
              chat_history_id: chatHistoryId ?? currentMessage.chat_history_id,
              has_feedback: hasFeedback ?? currentMessage.has_feedback,
            };

            const finalData: ChatData = { ...prev, messages };
            setToLocalStorage(storageKeys.chat, finalData);
            return finalData;
          }
        }

        const lastMessage = prev.messages[prev.messages.length - 1];
        if (lastMessage?.role === 'assistant' && answer && lastMessage.content === answer) {
          return prev;
        }

        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: answer,
          sources: uiSources,
          detailed_tasks: detailedTasks,
          timestamp: new Date().toISOString(),
          chat_history_id: chatHistoryId,
          has_feedback: hasFeedback,
        };

        const finalData: ChatData = {
          ...prev,
          messages: [...prev.messages, assistantMessage],
        };

        setToLocalStorage(storageKeys.chat, finalData);
        return finalData;
      });

      setIsLoading(false);
      setCurrentStep('router');
      streamingMessageIdRef.current = null;
    },
    [storageKeys.chat],
  );

  const appendTokenToStreamingMessage = useCallback(
    (token: string) => {
      if (!token) return;

      setChatData((prev) => {
        if (!prev) return prev;
        const updated = appendStreamingToken({
          prev,
          token,
          currentStreamingMessageId: streamingMessageIdRef.current,
          latestUiSources: latestUiSourcesRef.current,
          effectiveInitialQuery,
        });
        streamingMessageIdRef.current = updated.nextStreamingMessageId;
        return updated.nextData;
      });
    },
    [effectiveInitialQuery],
  );

  const applyStreamingSources = useCallback((sources: SourceResponse[] = []) => {
    latestSourcesRef.current = sources;
    latestUiSourcesRef.current = normalizeSources(sources);

    setChatData((prev) => {
      if (!prev) return prev;
      const updated = updateStreamingSources({
        prev,
        currentStreamingMessageId: streamingMessageIdRef.current,
        latestUiSources: latestUiSourcesRef.current,
      });
      streamingMessageIdRef.current = updated.nextStreamingMessageId;
      return updated.nextData;
    });
  }, []);

  const finalizeAfterStreamClose = useCallback(() => {
    if (isStopped()) {
      streamInFlightRef.current = false;
      return;
    }

    if (hasResultEventRef.current) {
      streamingMessageIdRef.current = null;
      streamInFlightRef.current = false;
      return;
    }

    setChatData((prev) => {
      if (!prev) return prev;

      const currentStreamingMessageId = streamingMessageIdRef.current;
      if (!currentStreamingMessageId) {
        if (hasStreamedTokenRef.current) {
          setToLocalStorage(storageKeys.chat, prev);
        }
        return prev;
      }

      const streamMessageIndex = prev.messages.findIndex((message) => message.id === currentStreamingMessageId);
      if (streamMessageIndex < 0) {
        if (hasStreamedTokenRef.current) {
          setToLocalStorage(storageKeys.chat, prev);
        }
        return prev;
      }

      const messages = [...prev.messages];
      const currentMessage = messages[streamMessageIndex];
      messages[streamMessageIndex] = {
        ...currentMessage,
        sources: latestUiSourcesRef.current.length ? latestUiSourcesRef.current : (currentMessage.sources ?? []),
        detailed_tasks: currentMessage.detailed_tasks ?? [],
      };

      const finalData: ChatData = { ...prev, messages };
      setToLocalStorage(storageKeys.chat, finalData);
      return finalData;
    });

    if (hasStreamedTokenRef.current) {
      refreshRecentChatsNow();
    }

    setIsLoading(false);
    setCurrentStep('router');
    streamingMessageIdRef.current = null;
    streamInFlightRef.current = false;
  }, [isStopped, refreshRecentChatsNow, storageKeys.chat]);

  /**
   * SSE 스트림 이벤트 핸들러
   */
  const handleStreamEvent = useCallback(
    (event: StreamEvent) => {
      if (isStopped()) return;

      switch (event.type) {
        case 'status': {
          const mappedStep = NODE_TO_UI_STEP[event.node];
          if (mappedStep === null || mappedStep === undefined) return;
          setCurrentStep(mappedStep);
          break;
        }

        case 'sources': {
          applyStreamingSources(event.sources ?? []);
          break;
        }

        case 'source_candidates': {
          applyStreamingSources(event.sources ?? []);
          break;
        }

        case 'token': {
          hasStreamedTokenRef.current = true;
          appendTokenToStreamingMessage(event.token);
          break;
        }

        case 'result': {
          hasResultEventRef.current = true;
          refreshRecentChatsNow();

          appendAssistantAnswer(
            event.answer,
            event.sources || [],
            event.related_jira_issues ?? [],
            event.chat_history_id,
            event.has_feedback,
          );
          break;
        }

        case 'error': {
          console.error('[useRagChat] stream error event:', event.message);
          setIsError(true);
          setIsLoading(false);
          streamInFlightRef.current = false;
          break;
        }

        case 'ping':
          break;

        default:
          break;
      }
    },
    [
      appendAssistantAnswer,
      appendTokenToStreamingMessage,
      applyStreamingSources,
      isStopped,
      refreshRecentChatsNow,
    ],
  );

  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || isLoading || !chatData || streamInFlightRef.current) return;

      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      };

      const updated: ChatData = {
        ...chatData,
        messages: [...chatData.messages, userMessage],
      };
      setChatData(updated);
      setToLocalStorage(storageKeys.chat, updated);
      refreshRecentChatsNow();

      beginAnswerLoading();

      try {
        await streamChat(message, handleStreamEvent);
        finalizeAfterStreamClose();
      } catch (err) {
        if ((err as Error).name === 'AbortError') {
          handleAbortError();
          return;
        }
        console.error('[useRagChat] sendMessage error:', err);
        setIsError(true);
        setIsLoading(false);
        streamInFlightRef.current = false;
      }
    },
    [
      beginAnswerLoading,
      chatData,
      finalizeAfterStreamClose,
      handleStreamEvent,
      handleAbortError,
      isLoading,
      refreshRecentChatsNow,
      storageKeys.chat,
      streamChat,
    ],
  );

  const submitEdit = useCallback(
    async (messageId: string, newContent: string) => {
      if (!chatData || streamInFlightRef.current) return;

      const targetIndex = chatData.messages.findIndex((message) => message.id === messageId);
      if (targetIndex === -1) return;

      const messagesBeforeTarget = chatData.messages.slice(0, targetIndex);
      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: newContent,
        timestamp: new Date().toISOString(),
      };

      const updated: ChatData = {
        ...chatData,
        messages: [...messagesBeforeTarget, userMessage],
      };
      setChatData(updated);
      setToLocalStorage(storageKeys.chat, updated);

      beginAnswerLoading();

      try {
        // 마지막 턴 soft-delete (실패해도 스트림 진행)
        try {
          await chatService.resetLastTurn(sessionId);
        } catch (resetErr) {
          console.warn('[useRagChat] resetLastTurn failed, proceeding with stream:', resetErr);
        }

        await streamChat(newContent, handleStreamEvent);
        finalizeAfterStreamClose();
      } catch (err) {
        if ((err as Error).name === 'AbortError') {
          handleAbortError();
          return;
        }
        console.error('[useRagChat] submitEdit error:', err);
        setIsError(true);
        setIsLoading(false);
        streamInFlightRef.current = false;
      }
    },
    [
      beginAnswerLoading,
      chatData,
      finalizeAfterStreamClose,
      handleAbortError,
      handleStreamEvent,
      sessionId,
      storageKeys.chat,
      streamChat,
    ],
  );

  const handleStop = useCallback(() => {
    if (!isLoading) return;

    markStopped();
    abortStream();

    setIsLoading(false);
    setIsError(false);
    setCurrentStep('router');

    if (!streamingMessageIdRef.current) {
      streamInFlightRef.current = false;
      appendAssistantAnswer('\n', [], []);
      return;
    }

    setChatData((prev) => {
      if (!prev) return prev;
      setToLocalStorage(storageKeys.chat, prev);
      return prev;
    });
    streamInFlightRef.current = false;
  }, [abortStream, appendAssistantAnswer, isLoading, markStopped, storageKeys.chat]);

  const updateMessageFeedback = useCallback(
    (messageId: string) => {
      setChatData((prev) => {
        if (!prev) return prev;

        const updatedMessages = prev.messages.map((message) =>
          message.id === messageId ? { ...message, has_feedback: true } : message,
        );

        const updatedData: ChatData = {
          ...prev,
          messages: updatedMessages,
        };

        setToLocalStorage(storageKeys.chat, updatedData);
        return updatedData;
      });
    },
    [storageKeys.chat],
  );

  useEffect(() => {
    if (!effectiveInitialQuery) return;

    const hasUserMessage = chatData?.messages.some((message) => message.role === 'user') ?? false;
    if (hasUserMessage) return;

    queueMicrotask(() => {
      ensureInitialUserMessage(effectiveInitialQuery);
      setIsLoading(true);
    });
  }, [chatData, effectiveInitialQuery, ensureInitialUserMessage]);

  useEffect(() => {
    if (!effectiveInitialQuery) return;
    if (streamInFlightRef.current) return;

    const hasAssistantContent =
      chatData?.messages.some((message) => message.role === 'assistant' && Boolean(message.content?.trim())) ?? false;
    if (hasAssistantContent) {
      clearPendingInitialQuery(sessionId);
      return;
    }

    const runStream = async () => {
      ensureInitialUserMessage(effectiveInitialQuery);
      beginAnswerLoading();
      clearPendingInitialQuery(sessionId);

      try {
        await streamChat(effectiveInitialQuery, handleStreamEvent);
        finalizeAfterStreamClose();
      } catch (err) {
        if ((err as Error).name === 'AbortError') {
          handleAbortError();
          return;
        }
        console.error('[useRagChat] fetchFirstAnswer error:', err);
        setIsError(true);
        setIsLoading(false);
        streamInFlightRef.current = false;
      }
    };

    void runStream();
  }, [
    beginAnswerLoading,
    ensureInitialUserMessage,
    finalizeAfterStreamClose,
    handleStreamEvent,
    handleAbortError,
    effectiveInitialQuery,
    chatData,
    isLoading,
    sessionId,
    streamChat,
  ]);

  return {
    chatData,
    isLoading,
    isError,
    currentStep,
    sendMessage,
    submitEdit,
    handleStop,
    setChatData,
    updateMessageFeedback,
  };
};

export default useRagChat;
