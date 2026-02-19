'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { NODE_TO_UI_STEP } from '@/features/chat/constants/config';
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
import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { ChatHistoryMessageResponse } from '@/shared/types/query/api';
import { isValidSessionId } from '@/shared/utils/sessionId';

const MESSAGE_PAGE_SIZE = 50;

interface UseRagChatOptions {
  sessionId: string;
  repo: string | null;
  initialQuery: string | null;
}

interface UseRagChatReturn {
  chatData: ChatData | null;
  resolvedSessionId: string | undefined;
  isLoading: boolean;
  isError: boolean;
  currentStep: RagUIStepKey;
  sendMessage: (message: string) => Promise<void>;
  submitEdit: (messageId: string, newContent: string) => Promise<void>;
  handleStop: () => void;
  setChatData: React.Dispatch<React.SetStateAction<ChatData | null>>;
  updateMessageFeedback: (messageId: string) => void;
}

const toComparableTimestamp = (iso: string) => {
  const parsed = new Date(iso).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
};

export const useRagChat = ({ sessionId, repo, initialQuery }: UseRagChatOptions): UseRagChatReturn => {
  const router = useRouter();
  const { streamChat, abortStream, markStopped, resetStopped, isStopped } = useRagStream();
  const queryClient = useQueryClient();

  const effectiveInitialQuery = initialQuery?.trim() ? initialQuery.trim() : null;
  const isPlaceholderSession = sessionId === 'new';
  const [provisionalSessionId, setProvisionalSessionId] = useState<string | undefined>();
  const resolvedSessionId = isPlaceholderSession ? provisionalSessionId : sessionId;

  const [chatData, setChatData] = useState<ChatData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(isValidSessionId(sessionId));
  const [isError, setIsError] = useState(false);
  const [currentStep, setCurrentStep] = useState<RagUIStepKey>('router');

  const syncedSessionRef = useRef<string | null>(null);
  const sessionSyncGuardRef = useRef<{ from: string; to: string } | null>(null);
  const pendingReplaceSessionIdRef = useRef<string | null>(null);

  const streamingMessageIdRef = useRef<string | null>(null);
  const hasStreamedTokenRef = useRef(false);
  const hasResultEventRef = useRef(false);
  const latestSourcesRef = useRef<SourceResponse[]>([]);
  const latestUiSourcesRef = useRef<ChatSource[]>([]);
  const streamInFlightRef = useRef(false);

  const refreshRecentChatsNow = useCallback(() => {
    refreshRecentChats(queryClient);
  }, [queryClient]);

  const resetStreamStateRefs = useCallback(() => {
    streamingMessageIdRef.current = null;
    hasStreamedTokenRef.current = false;
    hasResultEventRef.current = false;
    latestSourcesRef.current = [];
    latestUiSourcesRef.current = [];
  }, []);

  const buildEmptyChatData = useCallback(
    (targetSessionId: string): ChatData => ({
      session_id: targetSessionId,
      title: effectiveInitialQuery ?? '',
      repo: repo ?? '',
      messages: [],
    }),
    [effectiveInitialQuery, repo],
  );

  const toUiMessage = useCallback((item: ChatHistoryMessageResponse): Message => {
    const timestamp = item.created_at || new Date().toISOString();

    if (item.sender_type === 'human') {
      return {
        id: `history_${item.id}`,
        role: 'user',
        content: item.content ?? '',
        timestamp,
      };
    }

    const rawSources = Array.isArray(item.sources) ? (item.sources as SourceResponse[]) : [];

    return {
      id: `history_${item.id}`,
      role: 'assistant',
      content: item.content ?? '',
      sources: normalizeSources(rawSources),
      detailed_tasks: [],
      timestamp,
      chat_history_id: item.chat_history_id ? String(item.chat_history_id) : String(item.id),
      has_feedback: Boolean(item.has_feedback),
    };
  }, []);

  const loadSessionChatData = useCallback(
    async (targetSessionId: string): Promise<ChatData> => {
      let page = 1;
      let title = '';
      let total = 0;
      const allItems: ChatHistoryMessageResponse[] = [];

      while (true) {
        const response = await queryClient.fetchQuery(
          chatQueries.sessionMessages(targetSessionId, page, MESSAGE_PAGE_SIZE),
        );

        title = response.title || title;
        total = response.total;
        allItems.push(...response.items);

        if (allItems.length >= total || response.items.length === 0) {
          break;
        }

        page += 1;
      }

      const sortedMessages = [...allItems].sort((a, b) => {
        const byCreatedAt = toComparableTimestamp(a.created_at) - toComparableTimestamp(b.created_at);
        if (byCreatedAt !== 0) return byCreatedAt;
        return a.id - b.id;
      });

      return {
        session_id: targetSessionId,
        title: title || effectiveInitialQuery || '',
        repo: repo ?? '',
        messages: sortedMessages.map(toUiMessage),
      };
    },
    [effectiveInitialQuery, queryClient, repo, toUiMessage],
  );

  const syncChatDataFromServer = useCallback(
    async (targetSessionId: string) => {
      if (!isValidSessionId(targetSessionId)) return;

      try {
        const nextData = await loadSessionChatData(targetSessionId);
        setChatData(nextData);
      } catch (err) {
        console.error('[useRagChat] syncChatDataFromServer error:', err);
      }
    },
    [loadSessionChatData],
  );

  const resolveSessionIdFromStream = useCallback(
    (streamSessionId?: string) => {
      if (!streamSessionId) return;
      if (resolvedSessionId === streamSessionId) return;

      setProvisionalSessionId(streamSessionId);

      if (!isPlaceholderSession) return;
      if (pendingReplaceSessionIdRef.current === streamSessionId) return;

      sessionSyncGuardRef.current = { from: sessionId, to: streamSessionId };
      pendingReplaceSessionIdRef.current = streamSessionId;

      const nextUrl = (() => {
        if (typeof window === 'undefined') return `/chat/${streamSessionId}`;
        const params = new URLSearchParams(window.location.search);
        const queryString = params.toString();
        return queryString ? `/chat/${streamSessionId}?${queryString}` : `/chat/${streamSessionId}`;
      })();

      router.replace(nextUrl);
    },
    [isPlaceholderSession, resolvedSessionId, router, sessionId],
  );

  useEffect(() => {
    const previousSessionId = syncedSessionRef.current;
    if (previousSessionId === sessionId) return;

    const guard = sessionSyncGuardRef.current;
    if (guard && guard.from === previousSessionId && guard.to === sessionId) {
      syncedSessionRef.current = sessionId;
      sessionSyncGuardRef.current = null;
      pendingReplaceSessionIdRef.current = null;
      return;
    }

    syncedSessionRef.current = sessionId;

    streamInFlightRef.current = false;
    resetStreamStateRefs();
    abortStream();

    setIsError(false);
    setCurrentStep('router');

    if (!isValidSessionId(sessionId)) {
      setChatData(buildEmptyChatData(sessionId));
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    const hydrateSession = async () => {
      setIsLoading(true);
      setChatData(null);

      try {
        const nextData = await loadSessionChatData(sessionId);
        if (cancelled) return;
        setChatData(nextData);
      } catch (err) {
        if (cancelled) return;
        console.error('[useRagChat] loadSessionChatData error:', err);
        setIsError(true);
        setChatData(buildEmptyChatData(sessionId));
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void hydrateSession();

    return () => {
      cancelled = true;
    };
  }, [abortStream, buildEmptyChatData, loadSessionChatData, resetStreamStateRefs, sessionId]);

  const beginAnswerLoading = useCallback(() => {
    resetStopped();
    resetStreamStateRefs();
    streamInFlightRef.current = true;
    setIsLoading(true);
    setIsError(false);
    setCurrentStep('router');
  }, [resetStopped, resetStreamStateRefs]);

  const ensureInitialUserMessage = useCallback((query: string) => {
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

      return {
        ...prev,
        title: prev.title || trimmed,
        messages: [...prev.messages, userMessage],
      };
    });
  }, []);

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

            return { ...prev, messages };
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

        return {
          ...prev,
          messages: [...prev.messages, assistantMessage],
        };
      });

      setIsLoading(false);
      setCurrentStep('router');
      streamingMessageIdRef.current = null;
    },
    [],
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

  const finalizeAfterStreamClose = useCallback(async () => {
    if (isStopped()) {
      streamInFlightRef.current = false;
      return;
    }

    const targetSessionId = resolvedSessionId;

    if (hasResultEventRef.current) {
      if (targetSessionId) {
        await syncChatDataFromServer(targetSessionId);
      }
      streamingMessageIdRef.current = null;
      setIsLoading(false);
      setCurrentStep('router');
      streamInFlightRef.current = false;
      return;
    }

    if (hasStreamedTokenRef.current && targetSessionId) {
      await syncChatDataFromServer(targetSessionId);
      refreshRecentChatsNow();
    }

    setIsLoading(false);
    setCurrentStep('router');
    streamingMessageIdRef.current = null;
    streamInFlightRef.current = false;
  }, [isStopped, refreshRecentChatsNow, resolvedSessionId, syncChatDataFromServer]);

  const handleStreamEvent = useCallback(
    (event: StreamEvent) => {
      if ('session_id' in event) {
        resolveSessionIdFromStream(event.session_id);
      }
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
      resolveSessionIdFromStream,
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
      refreshRecentChatsNow();

      beginAnswerLoading();

      try {
        await streamChat(message, resolvedSessionId, handleStreamEvent);
        await finalizeAfterStreamClose();
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
      resolvedSessionId,
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

      beginAnswerLoading();

      try {
        try {
          if (resolvedSessionId) {
            await chatService.resetLastTurn(resolvedSessionId);
          }
        } catch (resetErr) {
          console.warn('[useRagChat] resetLastTurn failed, proceeding with stream:', resetErr);
        }

        await streamChat(newContent, resolvedSessionId, handleStreamEvent);
        await finalizeAfterStreamClose();
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
      resolvedSessionId,
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

    streamInFlightRef.current = false;
  }, [abortStream, appendAssistantAnswer, isLoading, markStopped]);

  const updateMessageFeedback = useCallback((messageId: string) => {
    setChatData((prev) => {
      if (!prev) return prev;

      const updatedMessages = prev.messages.map((message) =>
        message.id === messageId ? { ...message, has_feedback: true } : message,
      );

      return {
        ...prev,
        messages: updatedMessages,
      };
    });
  }, []);

  useEffect(() => {
    if (!effectiveInitialQuery) return;
    if (!chatData) return;

    const hasUserMessage = chatData.messages.some((message) => message.role === 'user');
    if (hasUserMessage) return;

    queueMicrotask(() => {
      ensureInitialUserMessage(effectiveInitialQuery);
      setIsLoading(true);
    });
  }, [chatData, effectiveInitialQuery, ensureInitialUserMessage]);

  useEffect(() => {
    if (!effectiveInitialQuery) return;
    if (!chatData) return;
    if (isLoading) return;
    if (streamInFlightRef.current) return;

    const hasAssistantContent = chatData.messages.some(
      (message) => message.role === 'assistant' && Boolean(message.content?.trim()),
    );
    if (hasAssistantContent) {
      return;
    }

    const runStream = async () => {
      ensureInitialUserMessage(effectiveInitialQuery);
      beginAnswerLoading();

      try {
        await streamChat(effectiveInitialQuery, resolvedSessionId, handleStreamEvent);
        await finalizeAfterStreamClose();
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
    chatData,
    effectiveInitialQuery,
    ensureInitialUserMessage,
    finalizeAfterStreamClose,
    handleAbortError,
    handleStreamEvent,
    isLoading,
    resolvedSessionId,
    streamChat,
  ]);

  return {
    chatData,
    resolvedSessionId,
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
