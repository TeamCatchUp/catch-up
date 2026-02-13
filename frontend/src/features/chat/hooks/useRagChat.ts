'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { getStorageKeys, NODE_TO_UI_STEP } from '@/features/chat/constants/config';
import { useRagStream } from '@/features/chat/hooks/useRagStream';
import type { BackendSource } from '@/features/chat/types/source';
import { normalizeSources } from '@/features/chat/utils/normalizeRagSources';
import { normalizeRelatedJiraIssues } from '@/features/chat/utils/normalizeRelatedJiraIssues';
import { MOCK_INITIAL_MESSAGES } from '@/shared/mocks/chat/data';
import { USE_MOCK } from '@/shared/mocks/config';
import { chatQueries } from '@/shared/queries/chatroom.queries';

interface UseRagChatOptions {
  sessionId: string;
  repo: string | null;
  initialQuery: string | null;
}

interface UseRagChatReturn {
  chatData: ChatData | null;
  isLoading: boolean;
  isError: boolean;
  currentStep: RagUIStepKey;
  prList: PRPayload[];
  showPRSelection: boolean;
  sendMessage: (message: string) => Promise<void>;
  submitEdit: (messageId: string, newContent: string) => Promise<void>;
  handlePRContinue: (selectedPrNumbers: number[]) => Promise<void>;
  handlePRRefetch: () => Promise<void>;
  handleStop: () => void;
  setChatData: React.Dispatch<React.SetStateAction<ChatData | null>>;
  updateMessageFeedback: (messageId: string) => void;
}

const loadSavedChat = (key: string): ChatData | null => {
  if (typeof window === 'undefined') return null;

  const saved = localStorage.getItem(key);
  if (!saved) return null;

  const parsedData: ChatData = JSON.parse(saved);
  const lastMessage = parsedData.messages[parsedData.messages.length - 1];

  if (lastMessage?.role === 'user') {
    const repairedData: ChatData = {
      ...parsedData,
      messages: [
        ...parsedData.messages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '',
          sources: [],
          detailed_tasks: [],
          timestamp: new Date().toISOString(),
        },
      ],
    };
    localStorage.setItem(key, JSON.stringify(repairedData));
    return repairedData;
  }

  return parsedData;
};

const buildInitialChatData = (
  sessionId: string,
  repo: string | null,
  initialQuery: string | null,
  storageKey: string,
): ChatData => {
  const saved = loadSavedChat(storageKey);
  if (saved) return saved;

  if (initialQuery) {
    return {
      session_id: sessionId,
      title: initialQuery,
      repo: repo || '',
      messages: [
        {
          id: crypto.randomUUID(),
          role: 'user',
          content: initialQuery,
          timestamp: new Date().toISOString(),
        },
      ],
    };
  }

  if (USE_MOCK) {
    return {
      session_id: sessionId,
      title: '로그인 인증 흐름을 설명해주세요',
      repo: repo || '',
      messages: MOCK_INITIAL_MESSAGES,
    };
  }

  return { session_id: sessionId, title: '', repo: repo || '', messages: [] };
};

export const useRagChat = ({
  sessionId,
  repo,
  initialQuery,
}: UseRagChatOptions): UseRagChatReturn => {
  const storageKeys = getStorageKeys(sessionId);
  const { streamChat, resumeStream, abortStream, markStopped, resetStopped, isStopped } =
    useRagStream(sessionId);
  const queryClient = useQueryClient();

  const [chatData, setChatData] = useState<ChatData | null>(() =>
    buildInitialChatData(sessionId, repo, initialQuery, storageKeys.chat),
  );
  const [isLoading, setIsLoading] = useState<boolean>(() => !loadSavedChat(storageKeys.chat) && !!initialQuery);
  const [isError, setIsError] = useState(false);
  const [currentStep, setCurrentStep] = useState<RagUIStepKey>('router');
  const [prList, setPrList] = useState<PRPayload[]>([]);
  const [showPRSelection, setShowPRSelection] = useState(false);
  const [prevSessionId, setPrevSessionId] = useState(sessionId);

  const streamingMessageIdRef = useRef<string | null>(null);
  const hasStreamedTokenRef = useRef(false);
  const hasResultEventRef = useRef(false);
  const wasInterruptedRef = useRef(false);
  const latestSourcesRef = useRef<BackendSource[]>([]);
  const latestUiSourcesRef = useRef<ChatSource[]>([]);

  const resetStreamStateRefs = useCallback(() => {
    streamingMessageIdRef.current = null;
    hasStreamedTokenRef.current = false;
    hasResultEventRef.current = false;
    wasInterruptedRef.current = false;
    latestSourcesRef.current = [];
    latestUiSourcesRef.current = [];
  }, []);

  if (prevSessionId !== sessionId) {
    setPrevSessionId(sessionId);

    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');

    const nextData = buildInitialChatData(sessionId, repo, initialQuery, storageKeys.chat);
    setChatData(nextData);

    const hasSaved = !!loadSavedChat(storageKeys.chat);
    setIsLoading(!hasSaved && !!initialQuery);
  }

  const beginAnswerLoading = useCallback(() => {
    resetStopped();
    resetStreamStateRefs();
    setIsLoading(true);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');
  }, [resetStopped, resetStreamStateRefs]);

  const appendAssistantAnswer = useCallback(
    (
      answer: string,
      sources: BackendSource[] = [],
      relatedJiraIssues: BackendSource[] = [],
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
              sources: uiSources.length ? uiSources : currentMessage.sources ?? [],
              detailed_tasks: detailedTasks,
              chat_history_id: chatHistoryId ?? currentMessage.chat_history_id,
              has_feedback: hasFeedback ?? currentMessage.has_feedback,
            };

            const finalData: ChatData = { ...prev, messages };
            localStorage.setItem(storageKeys.chat, JSON.stringify(finalData));
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

        localStorage.setItem(storageKeys.chat, JSON.stringify(finalData));
        return finalData;
      });

      setIsLoading(false);
      setShowPRSelection(false);
      setCurrentStep('router');
      streamingMessageIdRef.current = null;
    },
    [storageKeys.chat],
  );

  const appendTokenToStreamingMessage = useCallback((token: string) => {
    if (!token) return;

    setChatData((prev) => {
      if (!prev) return prev;

      const currentStreamingMessageId = streamingMessageIdRef.current;
      if (currentStreamingMessageId) {
        const streamMessageIndex = prev.messages.findIndex((message) => message.id === currentStreamingMessageId);

        if (streamMessageIndex >= 0) {
          const messages = [...prev.messages];
          const currentMessage = messages[streamMessageIndex];
          messages[streamMessageIndex] = {
            ...currentMessage,
            content: `${currentMessage.content}${token}`,
            sources: latestUiSourcesRef.current,
            detailed_tasks: currentMessage.detailed_tasks ?? [],
          };
          return { ...prev, messages };
        }
      }

      const messageId = crypto.randomUUID();
      streamingMessageIdRef.current = messageId;

      const assistantMessage: Message = {
        id: messageId,
        role: 'assistant',
        content: token,
        sources: latestUiSourcesRef.current,
        detailed_tasks: [],
        timestamp: new Date().toISOString(),
      };

      return {
        ...prev,
        messages: [...prev.messages, assistantMessage],
      };
    });
  }, []);

  const applyStreamingSources = useCallback((sources: BackendSource[] = []) => {
    latestSourcesRef.current = sources;
    latestUiSourcesRef.current = normalizeSources(sources);

    const currentStreamingMessageId = streamingMessageIdRef.current;
    if (!currentStreamingMessageId) return;

    setChatData((prev) => {
      if (!prev) return prev;

      const streamMessageIndex = prev.messages.findIndex((message) => message.id === currentStreamingMessageId);
      if (streamMessageIndex < 0) return prev;

      const messages = [...prev.messages];
      const currentMessage = messages[streamMessageIndex];
      messages[streamMessageIndex] = {
        ...currentMessage,
        sources: latestUiSourcesRef.current,
      };

      return { ...prev, messages };
    });
  }, []);

  const finalizeAfterStreamClose = useCallback(() => {
    if (isStopped()) return;
    if (wasInterruptedRef.current) return;

    if (hasResultEventRef.current) {
      streamingMessageIdRef.current = null;
      return;
    }

    setChatData((prev) => {
      if (!prev) return prev;

      const currentStreamingMessageId = streamingMessageIdRef.current;
      if (!currentStreamingMessageId) {
        if (hasStreamedTokenRef.current) {
          localStorage.setItem(storageKeys.chat, JSON.stringify(prev));
        }
        return prev;
      }

      const streamMessageIndex = prev.messages.findIndex((message) => message.id === currentStreamingMessageId);
      if (streamMessageIndex < 0) {
        if (hasStreamedTokenRef.current) {
          localStorage.setItem(storageKeys.chat, JSON.stringify(prev));
        }
        return prev;
      }

      const messages = [...prev.messages];
      const currentMessage = messages[streamMessageIndex];
      messages[streamMessageIndex] = {
        ...currentMessage,
        sources: latestUiSourcesRef.current.length ? latestUiSourcesRef.current : currentMessage.sources ?? [],
        detailed_tasks: currentMessage.detailed_tasks ?? [],
      };

      const finalData: ChatData = { ...prev, messages };
      localStorage.setItem(storageKeys.chat, JSON.stringify(finalData));
      return finalData;
    });

    if (hasStreamedTokenRef.current) {
      window.dispatchEvent(new Event('refresh_sidebar'));
      void queryClient.invalidateQueries({ queryKey: chatQueries.lists() });
    }

    setIsLoading(false);
    setShowPRSelection(false);
    setCurrentStep('router');
    streamingMessageIdRef.current = null;
  }, [isStopped, queryClient, storageKeys.chat]);

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

        case 'token': {
          hasStreamedTokenRef.current = true;
          appendTokenToStreamingMessage(event.token);
          break;
        }

        case 'interrupt': {
          wasInterruptedRef.current = true;
          setPrList(event.payload);
          setShowPRSelection(true);
          setIsLoading(false);
          abortStream();
          break;
        }

        case 'result': {
          hasResultEventRef.current = true;
          window.dispatchEvent(new Event('refresh_sidebar'));
          void queryClient.invalidateQueries({ queryKey: chatQueries.lists() });

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
          break;
        }

        case 'ping':
          break;

        default:
          break;
      }
    },
    [
      abortStream,
      appendAssistantAnswer,
      appendTokenToStreamingMessage,
      applyStreamingSources,
      isStopped,
      queryClient,
    ],
  );

  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || isLoading || !chatData) return;

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
      localStorage.setItem(storageKeys.chat, JSON.stringify(updated));

      beginAnswerLoading();

      try {
        await streamChat(message, handleStreamEvent);
        finalizeAfterStreamClose();
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('[useRagChat] sendMessage error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [
      beginAnswerLoading,
      chatData,
      finalizeAfterStreamClose,
      handleStreamEvent,
      isLoading,
      storageKeys.chat,
      streamChat,
    ],
  );

  const submitEdit = useCallback(
    async (messageId: string, newContent: string) => {
      if (!chatData) return;

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
      localStorage.setItem(storageKeys.chat, JSON.stringify(updated));

      beginAnswerLoading();

      try {
        await streamChat(newContent, handleStreamEvent);
        finalizeAfterStreamClose();
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('[useRagChat] submitEdit error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [beginAnswerLoading, chatData, finalizeAfterStreamClose, handleStreamEvent, storageKeys.chat, streamChat],
  );

  const handlePRContinue = useCallback(
    async (selectedPrNumbers: number[]) => {
      setShowPRSelection(false);
      beginAnswerLoading();

      const selectedPRs = selectedPrNumbers
        .map((prNumber) => prList.find((pr) => pr.pr_number === prNumber))
        .filter((pr): pr is PRPayload => pr !== undefined)
        .map((pr) => ({
          pr_number: pr.pr_number,
          repo_name: pr.repo_name,
          owner: pr.owner,
        }));

      try {
        await resumeStream(selectedPRs, handleStreamEvent);
        finalizeAfterStreamClose();
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('[useRagChat] handlePRContinue error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [beginAnswerLoading, finalizeAfterStreamClose, handleStreamEvent, prList, resumeStream],
  );

  const handlePRRefetch = useCallback(async () => {
    if (!chatData) return;

    const lastUserMessage = [...chatData.messages].reverse().find((message) => message.role === 'user');
    const query = lastUserMessage?.content?.trim();
    if (!query) return;

    abortStream();
    beginAnswerLoading();

    try {
      await streamChat(query, handleStreamEvent);
      finalizeAfterStreamClose();
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      console.error('[useRagChat] handlePRRefetch error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  }, [abortStream, beginAnswerLoading, chatData, finalizeAfterStreamClose, handleStreamEvent, streamChat]);

  const handleStop = useCallback(() => {
    if (!isLoading) return;

    markStopped();
    abortStream();

    setIsLoading(false);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');

    if (!streamingMessageIdRef.current) {
      appendAssistantAnswer('\n', [], []);
      return;
    }

    setChatData((prev) => {
      if (!prev) return prev;
      localStorage.setItem(storageKeys.chat, JSON.stringify(prev));
      return prev;
    });
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

        localStorage.setItem(storageKeys.chat, JSON.stringify(updatedData));
        return updatedData;
      });
    },
    [storageKeys.chat],
  );

  useEffect(() => {
    resetStreamStateRefs();
    abortStream();
  }, [abortStream, resetStreamStateRefs, sessionId]);

  useEffect(() => {
    if (localStorage.getItem(storageKeys.chat) || !initialQuery) return;

    resetStopped();
    resetStreamStateRefs();

    const runStream = async () => {
      try {
        await streamChat(initialQuery, handleStreamEvent);
        finalizeAfterStreamClose();
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('[useRagChat] fetchFirstAnswer error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    };

    void runStream();
  }, [
    finalizeAfterStreamClose,
    handleStreamEvent,
    initialQuery,
    resetStopped,
    resetStreamStateRefs,
    storageKeys.chat,
    streamChat,
  ]);

  return {
    chatData,
    isLoading,
    isError,
    currentStep,
    prList,
    showPRSelection,
    sendMessage,
    submitEdit,
    handlePRContinue,
    handlePRRefetch,
    handleStop,
    setChatData,
    updateMessageFeedback,
  };
};

export default useRagChat;
