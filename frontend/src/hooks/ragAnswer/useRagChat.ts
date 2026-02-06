/**
 * useRagChat
 * SSE 연결, 메시지 전송/수신, 채팅 상태 관리
 */

'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { createSSEConnection, sendChatQuery, resumeChatQuery } from '@/util/ragAnswer/sendChatQuery';
import { normalizeSources } from '@/util/ragAnswer/normalizeRagSources';
import { normalizeRelatedJiraIssues } from '@/util/ragAnswer/normalizeRelatedJiraIssues';
import { NODE_TO_UI_STEP, HARD_CODED_INDEX_LIST, SSE_CONFIG, getStorageKeys } from '@/constants/ragAnswer/config';

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

export const useRagChat = ({
  sessionId,
  repo,
  initialQuery,
}: UseRagChatOptions): UseRagChatReturn => {
  // Storage Keys
  const storageKeys = getStorageKeys(sessionId);

  // Chat State
  const [chatData, setChatData] = useState<ChatData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [currentStep, setCurrentStep] = useState<RagUIStepKey>('router');

  // PR Selection State
  const [prList, setPrList] = useState<PRPayload[]>([]);
  const [showPRSelection, setShowPRSelection] = useState(false);

  // Refs
  const sseRef = useRef<EventSource | null>(null);
  const stoppedRef = useRef(false);

  /** SSE 연결 종료 */
  const closeSSEConnection = useCallback(() => {
    if (sseRef.current) {
      console.log('[useRagChat] SSE 연결 종료');
      sseRef.current.close();
      sseRef.current = null;
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

  /** SSE 메시지 핸들러 */
  const handleSSEMessage = useCallback(
    (notification: RagNotification) => {
      if (stoppedRef.current) return;

      if (!notification?.data || notification.data.sessionId !== sessionId) {
        return;
      }

      const { type, data } = notification;

      switch (type) {
        case 'RAG_IN_PROGRESS': {
          if (data.type !== 'status') return;

          const mappedStep = NODE_TO_UI_STEP[data.node];
          if (mappedStep === null) return;

          console.log('[useRagChat] Step update:', data.node, '->', mappedStep);
          setCurrentStep(mappedStep);
          break;
        }

        case 'RAG_INTERRUPT': {
          if (data.node !== 'manage_pr_context' || !data.payload) return;

          console.log('[useRagChat] RAG_INTERRUPT payload length:', data.payload.length);

          setPrList(data.payload);
          setShowPRSelection(true);
          setIsLoading(false);
          closeSSEConnection();
          break;
        }

        case 'RAG_DONE': {
          window.dispatchEvent(new Event('refresh_sidebar'));
          console.log('[useRagChat] RAG_DONE received');

          const response = data.response;
          if (!response) {
            console.error('[useRagChat] RAG_DONE but no response');
            setIsError(true);
            setIsLoading(false);
            closeSSEConnection();
            return;
          }

          const related = data.relatedJiraIssues ?? [];
          appendAssistantAnswer(
            response.answer,
            response.sources || [],
            related,
            response.chatHistoryId,
            response.hasFeedback,
          );

          closeSSEConnection();
          break;
        }

        default:
          break;
      }
    },
    [sessionId, appendAssistantAnswer, closeSSEConnection],
  );

  /** SSE 연결 및 쿼리 전송 */
  const connectSSEAndSendQuery = useCallback(
    async (query: string, indexList: string[], isResume = false, resumePayload?: any) => {
      return new Promise<void>((resolve, reject) => {
        console.log('[useRagChat] SSE 연결 시작');
        closeSSEConnection();

        let chatRequestSent = false;

        const timeout = setTimeout(() => {
          if (!chatRequestSent) {
            console.error('[useRagChat] 타임아웃 - 30초 내 응답 없음');
            closeSSEConnection();
            reject(new Error('SSE connection timeout'));
          }
        }, SSE_CONFIG.TIMEOUT_MS);

        const sse = createSSEConnection(
          sessionId,
          handleSSEMessage,
          (err) => {
            console.error('[useRagChat] SSE error:', err);
            if (!chatRequestSent) {
              clearTimeout(timeout);
              closeSSEConnection();
              reject(err);
            }
          },
          async () => {
            console.log('[useRagChat] SSE 연결 완료');

            try {
              if (isResume) {
                await resumeChatQuery(sessionId, resumePayload);
              } else {
                await sendChatQuery(query, sessionId, indexList);
              }
              chatRequestSent = true;
              resolve();
            } catch (err) {
              console.error('[useRagChat] 채팅 요청 실패:', err);
              clearTimeout(timeout);
              closeSSEConnection();
              reject(err);
            }
          },
        );

        sseRef.current = sse;
      });
    },
    [sessionId, handleSSEMessage, closeSSEConnection],
  );

  /** 메시지 전송 */
  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || isLoading || !chatData) return;

      const indexList = [...HARD_CODED_INDEX_LIST];

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
        await connectSSEAndSendQuery(message, indexList);
      } catch (err) {
        console.error('[useRagChat] sendMessage Error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [isLoading, chatData, sessionId, beginAnswerLoading, connectSSEAndSendQuery],
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

      const indexList = [...HARD_CODED_INDEX_LIST];

      try {
        await connectSSEAndSendQuery(newContent, indexList);
      } catch (err) {
        console.error('[useRagChat] submitEdit Error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [chatData, beginAnswerLoading, connectSSEAndSendQuery],
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
        await connectSSEAndSendQuery('', [], true, selectedPRs);
      } catch (err) {
        console.error('[useRagChat] handlePRContinue Error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    },
    [prList, beginAnswerLoading, connectSSEAndSendQuery],
  );

  /** PR 목록 다시 가져오기 */
  const handlePRRefetch = useCallback(async () => {
    if (!chatData) return;

    const lastUser = [...chatData.messages].reverse().find((m) => m.role === 'user');
    const query = lastUser?.content?.trim();
    if (!query) return;

    closeSSEConnection();
    beginAnswerLoading();

    try {
      await connectSSEAndSendQuery(query, [...HARD_CODED_INDEX_LIST]);
    } catch (err) {
      console.error('[useRagChat] handlePRRefetch Error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  }, [chatData, closeSSEConnection, beginAnswerLoading, connectSSEAndSendQuery]);

  /** 응답 생성 중지 */
  const handleStop = useCallback(() => {
    if (!isLoading) return;

    stoppedRef.current = true;

    setIsLoading(false);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');

    closeSSEConnection();
    appendAssistantAnswer('\n', [], []);
  }, [isLoading, appendAssistantAnswer, closeSSEConnection]);

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

  /** 초기 데이터 로드 */
  useEffect(() => {
    const fetchFirstAnswer = async (query: string) => {
      beginAnswerLoading();

      const indexList = [...HARD_CODED_INDEX_LIST];

      const initialData: ChatData = {
        sessionId,
        title: query,
        repo: repo || '',
        messages: [
          {
            id: crypto.randomUUID(),
            role: 'user',
            content: query,
            timestamp: new Date().toISOString(),
          },
        ],
      };

      setChatData(initialData);

      try {
        await connectSSEAndSendQuery(query, indexList);
      } catch (err) {
        console.error('[useRagChat] fetchFirstAnswer Error:', err);
        setIsError(true);
        setIsLoading(false);
      }
    };

    const saved = localStorage.getItem(storageKeys.chat);

    if (saved) {
      const parsedData: ChatData = JSON.parse(saved);
      const lastMessage = parsedData.messages[parsedData.messages.length - 1];

      if (lastMessage?.role === 'user') {
        // 답변을 받지 못한 상태 - 에러 메시지 추가
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

        setChatData(errorData);
        localStorage.setItem(storageKeys.chat, JSON.stringify(errorData));
        setIsLoading(false);
        return;
      }

      setChatData(parsedData);
      setIsLoading(false);
      return;
    }

    if (initialQuery) {
      fetchFirstAnswer(initialQuery);
      return;
    }

    setChatData({
      sessionId,
      title: '',
      repo: repo || '',
      messages: [],
    });
  }, [sessionId, initialQuery, repo, storageKeys.chat, beginAnswerLoading, connectSSEAndSendQuery]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeSSEConnection();
    };
  }, [closeSSEConnection]);

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
