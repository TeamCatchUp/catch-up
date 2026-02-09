/**
 * useRagChat
 * fetch ReadableStream SSE, 메시지 전송/수신, 채팅 상태 관리
 */

'use client';

import { useCallback, useEffect,useRef, useState } from 'react';

import { getStorageKeys,NODE_TO_UI_STEP } from '@/features/chat/constants/config';
import chatService from '@/features/chat/services/chatService';
import { normalizeSources } from '@/features/chat/utils/normalizeRagSources';
import { normalizeRelatedJiraIssues } from '@/features/chat/utils/normalizeRelatedJiraIssues';

interface UseRagChatOptions {
  sessionId: string;
  repo: string | null;
  initialQuery: string | null;
}

interface UseRagChatReturn {
  // State
  chatData: ChatData | null;
  isLoading: boolean;
  isError: boolean;
  currentStep: RagUIStepKey;
  prList: PRPayload[];
  showPRSelection: boolean;

  // Actions
  sendMessage: (message: string) => Promise<void>;
  submitEdit: (messageId: string, newContent: string) => Promise<void>;
  handlePRContinue: (selectedPrNumbers: number[]) => Promise<void>;
  handlePRRefetch: () => Promise<void>;
  handleStop: () => void;
  setChatData: React.Dispatch<React.SetStateAction<ChatData | null>>;
  updateMessageFeedback: (messageId: string) => void;
}

/** Read + repair saved chat from localStorage */
const loadSavedChat = (key: string): ChatData | null => {
  const saved = localStorage.getItem(key);
  if (!saved) return null;

  const parsedData: ChatData = JSON.parse(saved);
  const lastMessage = parsedData.messages[parsedData.messages.length - 1];

  if (lastMessage?.role === 'user') {
    const errorData: ChatData = {
      ...parsedData,
      messages: [
        ...parsedData.messages,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: '',
          sources: [],
          detailedTasks: [],
          timestamp: new Date().toISOString(),
        },
      ],
    };
    localStorage.setItem(key, JSON.stringify(errorData));
    return errorData;
  }

  return parsedData;
};

export const useRagChat = ({
  sessionId,
  repo,
  initialQuery,
}: UseRagChatOptions): UseRagChatReturn => {
  // Storage Keys
  const storageKeys = getStorageKeys(sessionId);

  // Chat State - initialize from localStorage
  const [chatData, setChatData] = useState<ChatData | null>(() => {
    const saved = loadSavedChat(storageKeys.chat);
    if (saved) return saved;
    if (initialQuery) {
      return {
        sessionId,
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
    return { sessionId, title: '', repo: repo || '', messages: [] };
  });
  const [isLoading, setIsLoading] = useState(
    () => !localStorage.getItem(storageKeys.chat) && !!initialQuery,
  );
  const [isError, setIsError] = useState(false);
  const [currentStep, setCurrentStep] = useState<RagUIStepKey>('router');

  // PR Selection State
  const [prList, setPrList] = useState<PRPayload[]>([]);
  const [showPRSelection, setShowPRSelection] = useState(false);

  // Refs
  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);

  // Handle session change (adjusting state during render)
  const [prevSessionId, setPrevSessionId] = useState(sessionId);
  if (prevSessionId !== sessionId) {
    setPrevSessionId(sessionId);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');

    const saved = loadSavedChat(storageKeys.chat);
    if (saved) {
      setChatData(saved);
      setIsLoading(false);
    } else if (initialQuery) {
      setChatData({
        sessionId,
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
      });
      setIsLoading(true);
    } else {
      setChatData({ sessionId, title: '', repo: repo || '', messages: [] });
      setIsLoading(false);
    }
  }

  /** 스트림 중단 */
  const abortStream = useCallback(() => {
    if (abortRef.current) {
      console.log('[useRagChat] 스트림 중단');
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  /** 답변 로딩 시작 */
  const beginAnswerLoading = useCallback(() => {
    stoppedRef.current = false;
    setIsLoading(true);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');
  }, []);

  /** 어시스턴트 답변 추가 */
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

        // 중복 체크: 마지막 메시지가 동일한 내용이면 무시
        const lastMessage = prev.messages[prev.messages.length - 1];
        if (lastMessage?.role === 'assistant' && lastMessage?.content === answer) {
          console.warn('[useRagChat] 중복 답변 무시');
          return prev;
        }

        const uiSources = normalizeSources(sources);
        const detailedTasks = normalizeRelatedJiraIssues(relatedJiraIssues);

        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: answer,
          sources: uiSources,
          detailedTasks,
          timestamp: new Date().toISOString(),
          chatHistoryId,
          hasFeedback,
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
    },
    [storageKeys.chat],
  );

  /** StreamEvent 핸들러 */
  const handleStreamEvent = useCallback(
    (event: StreamEvent) => {
      if (stoppedRef.current) return;

      switch (event.type) {
        case 'status': {
          const mappedStep = NODE_TO_UI_STEP[event.node];
          if (mappedStep === null || mappedStep === undefined) return;

          console.log('[useRagChat] Step update:', event.node, '->', mappedStep);
          setCurrentStep(mappedStep);
          break;
        }

        case 'interrupt': {
          console.log('[useRagChat] interrupt payload length:', event.payload.length);
          setPrList(event.payload);
          setShowPRSelection(true);
          setIsLoading(false);
          abortStream();
          break;
        }

        case 'result': {
          window.dispatchEvent(new Event('refresh_sidebar'));
          console.log('[useRagChat] result received');

          appendAssistantAnswer(
            event.answer,
            event.sources || [],
            event.relatedJiraIssues ?? [],
            event.chatHistoryId,
            event.hasFeedback,
          );
          break;
        }

        case 'ping':
          break;

        default:
          break;
      }
    },
    [appendAssistantAnswer, abortStream],
  );

  /** 스트림 채팅 전송 */
  const streamAndSendQuery = useCallback(
    async (query: string, isResume = false, resumePayload?: { prNumber: number; repoName: string; owner: string }[]) => {
      abortStream();

      const controller = new AbortController();
      abortRef.current = controller;

      if (isResume && resumePayload) {
        await chatService.resumeStream(sessionId, resumePayload, handleStreamEvent, controller.signal);
      } else {
        await chatService.streamChat(query, sessionId, handleStreamEvent, controller.signal);
      }
    },
    [sessionId, handleStreamEvent, abortStream],
  );

  /** 메시지 전송 */
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
        await streamAndSendQuery(message);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('[useRagChat] sendMessage Error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [isLoading, chatData, storageKeys.chat, beginAnswerLoading, streamAndSendQuery],
  );

  /** 메시지 수정 제출 */
  const submitEdit = useCallback(
    async (messageId: string, newContent: string) => {
      if (!chatData) return;

      const idx = chatData.messages.findIndex((m) => m.id === messageId);
      if (idx === -1) return;

      const trimmed = chatData.messages.slice(0, idx);

      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: newContent,
        timestamp: new Date().toISOString(),
      };

      const updated: ChatData = {
        ...chatData,
        messages: [...trimmed, userMessage],
      };
      setChatData(updated);

      beginAnswerLoading();

      try {
        await streamAndSendQuery(newContent);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('[useRagChat] submitEdit Error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [chatData, beginAnswerLoading, streamAndSendQuery],
  );

  /** PR 선택 후 계속 진행 */
  const handlePRContinue = useCallback(
    async (selectedPrNumbers: number[]) => {
      console.log('[useRagChat] PR Continue:', selectedPrNumbers);

      setShowPRSelection(false);
      beginAnswerLoading();

      const selectedPRs = selectedPrNumbers
        .map((prNumber) => prList.find((p) => p.prNumber === prNumber))
        .filter((pr): pr is PRPayload => pr !== undefined)
        .map((pr) => ({
          prNumber: pr.prNumber,
          repoName: pr.repoName,
          owner: pr.owner,
        }));

      try {
        await streamAndSendQuery('', true, selectedPRs);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('[useRagChat] handlePRContinue Error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [prList, beginAnswerLoading, streamAndSendQuery],
  );

  /** PR 목록 다시 가져오기 */
  const handlePRRefetch = useCallback(async () => {
    if (!chatData) return;

    const lastUser = [...chatData.messages].reverse().find((m) => m.role === 'user');
    const query = lastUser?.content?.trim();
    if (!query) return;

    abortStream();
    beginAnswerLoading();

    try {
      await streamAndSendQuery(query);
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      console.error('[useRagChat] handlePRRefetch Error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  }, [chatData, abortStream, beginAnswerLoading, streamAndSendQuery]);

  /** 응답 생성 중지 */
  const handleStop = useCallback(() => {
    if (!isLoading) return;

    stoppedRef.current = true;

    setIsLoading(false);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');

    abortStream();
    appendAssistantAnswer('\n', [], []);
  }, [isLoading, appendAssistantAnswer, abortStream]);

  /** 메시지 피드백 상태 업데이트 */
  const updateMessageFeedback = useCallback(
    (messageId: string) => {
      setChatData((prev) => {
        if (!prev) return prev;

        const updatedMessages = prev.messages.map((msg) =>
          msg.id === messageId ? { ...msg, hasFeedback: true } : msg,
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

  /** 초기 스트리밍 시작 (저장된 데이터 없고 initialQuery 있을 때만) */
  useEffect(() => {
    if (localStorage.getItem(storageKeys.chat) || !initialQuery) return;

    stoppedRef.current = false;

    const runStream = async () => {
      try {
        await streamAndSendQuery(initialQuery);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('[useRagChat] fetchFirstAnswer Error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    };
    runStream();
  }, [sessionId, initialQuery, storageKeys.chat, streamAndSendQuery]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortStream();
    };
  }, [abortStream]);

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
