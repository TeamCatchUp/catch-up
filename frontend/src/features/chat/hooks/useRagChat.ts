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
  PRPayload,
  RagUIStepKey,
  SourceResponse,
  StreamEvent,
} from '@/features/chat/types';
import { normalizeSources } from '@/features/chat/utils/normalize/normalizeRagSources';
import { normalizeRelatedJiraIssues } from '@/features/chat/utils/normalize/normalizeRelatedJiraIssues';

/**
 * RAG 채팅 훅 옵션
 * @interface UseRagChatOptions
 * @property {string} sessionId - 현재 세션 ID (URL 파라미터로 전달)
 * @property {string | null} repo - 저장소 정보 (사용자가 선택한 repo)
 * @property {string | null} initialQuery - 초기 질문 (URL 쿼리 파라미터 또는 sessionStorage에서 가져옴)
 */
interface UseRagChatOptions {
  sessionId: string;
  repo: string | null;
  initialQuery: string | null;
}

/**
 * RAG 채팅 훅 반환 타입
 * @interface UseRagChatReturn
 * @property {ChatData | null} chatData - 현재 채팅 세션의 전체 데이터 (메시지 배열 포함)
 * @property {boolean} isLoading - 답변 생성 중 여부
 * @property {boolean} isError - 에러 발생 여부
 * @property {RagUIStepKey} currentStep - 현재 RAG 처리 단계 (router, rewrite, search 등)
 * @property {PRPayload[]} prList - PR 선택 interrupt 시 표시할 PR 목록
 * @property {boolean} showPRSelection - PR 선택 모달 표시 여부
 * @property {(message: string) => Promise<void>} sendMessage - 새 질문 전송
 * @property {(messageId: string, newContent: string) => Promise<void>} submitEdit - 기존 질문 수정 후 재전송
 * @property {(selectedPrNumbers: number[]) => Promise<void>} handlePRContinue - PR 선택 후 스트림 재개
 * @property {(void) => Promise<void>} handlePRRefetch - PR 다시 가져오기 (스트림 재시작)
 * @property {() => void} handleStop - 스트림 중단 (사용자 요청)
 * @property {React.Dispatch<React.SetStateAction<ChatData | null>>} setChatData - 채팅 데이터 직접 수정
 * @property {(messageId: string) => void} updateMessageFeedback - 메시지의 피드백 상태 업데이트
 */
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

/**
 * RAG 채팅 통합 관리 훅
 *
 * 채팅 세션의 전체 lifecycle을 관리하는 중앙 훅
 * - SSE 스트림 연결 및 이벤트 처리
 * - 메시지 상태 관리 (user/assistant)
 * - localStorage 기반 세션 영속화
 * - PR 선택 interrupt 처리
 * - 스트림 중단 및 재개
 *
 * @param options - 훅 옵션
 * @param options.sessionId - 현재 세션 ID
 * @param options.repo - 저장소 정보
 * @param options.initialQuery - 초기 질문
 * @returns RAG 채팅 상태 및 핸들러
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
  const [prList, setPrList] = useState<PRPayload[]>([]);
  const [showPRSelection, setShowPRSelection] = useState(false);
  const syncedSessionRef = useRef(sessionId);

  const refreshRecentChatsNow = useCallback(() => {
    refreshRecentChats(queryClient);
  }, [queryClient]);

  /**
   * 스트림 진행 상태 추적 ref들
   * React state가 아닌 ref를 사용하여 렌더링 트리거 없이 상태 추적
   */
  const streamingMessageIdRef = useRef<string | null>(null); // 현재 스트리밍 중인 메시지 ID
  const hasStreamedTokenRef = useRef(false); // 토큰을 하나라도 받았는지 여부 (사이드바 갱신 판단)
  const hasResultEventRef = useRef(false); // result 이벤트를 받았는지 여부 (최종 완료 판단)
  const wasInterruptedRef = useRef(false); // PR 선택 interrupt가 발생했는지 여부
  const latestSourcesRef = useRef<SourceResponse[]>([]); // 가장 최근에 받은 백엔드 소스 (원본)
  const latestUiSourcesRef = useRef<ChatSource[]>([]); // 가장 최근에 받은 UI용 소스 (정규화됨)
  const streamInFlightRef = useRef(false); // 스트림 진행 중 여부 (중복 요청 방지)

  /**
   * 스트림 상태 ref들을 초기화
   * 새 스트림 시작 전 또는 에러 후 호출
   */
  const resetStreamStateRefs = useCallback(() => {
    streamingMessageIdRef.current = null;
    hasStreamedTokenRef.current = false;
    hasResultEventRef.current = false;
    wasInterruptedRef.current = false;
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
      setShowPRSelection(false);
      setCurrentStep('router');
      setChatData(nextData);
      setIsLoading(!hasSaved && !!effectiveInitialQuery);
    });
  }, [abortStream, effectiveInitialQuery, repo, resetStreamStateRefs, sessionId, storageKeys.chat]);

  /**
   * 답변 생성 시작 시 상태 초기화
   * 새 질문 또는 질문 수정 시 호출
   */
  const beginAnswerLoading = useCallback(() => {
    resetStopped();
    resetStreamStateRefs();
    streamInFlightRef.current = true;
    setIsLoading(true);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');
  }, [resetStopped, resetStreamStateRefs]);

  /**
   * 초기 질문이 있는데 user 메시지가 없는 경우 user 메시지 추가
   * initialQuery로 시작하는 세션에서 호출
   */
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

        localStorage.setItem(storageKeys.chat, JSON.stringify(nextData));
        return nextData;
      });
    },
    [storageKeys.chat],
  );

  /**
   * AbortError 처리 (사용자가 스트림 중단했을 때)
   * 사용자가 명시적으로 중단한 경우(isStopped)는 무시
   * PR interrupt인 경우는 loading만 해제
   * 그 외는 에러로 간주하지 않고 정상 종료 처리
   */
  const handleAbortError = useCallback(() => {
    streamInFlightRef.current = false;

    if (isStopped()) return;
    if (wasInterruptedRef.current) {
      setIsLoading(false);
      return;
    }

    setIsLoading(false);
    setCurrentStep('router');
  }, [isStopped]);

  /**
   * assistant 답변 메시지 추가 또는 업데이트
   * - 스트리밍 중인 메시지가 있으면 업데이트
   * - 없으면 새 메시지 추가
   * - localStorage에 자동 저장
   *
   * @param answer - 답변 내용
   * @param sources - 출처 목록 (백엔드 원본)
   * @param relatedJiraIssues - 관련 Jira 이슈
   * @param chatHistoryId - 백엔드 채팅 히스토리 ID
   * @param hasFeedback - 피드백 존재 여부
   */
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

  /**
   * 스트리밍 메시지에 토큰 추가 (실시간 답변 생성)
   * - 현재 스트리밍 중인 메시지에 토큰 누적
   * - 메시지가 없으면 새로 생성
   * - user 메시지가 없으면 fallback으로 추가
   *
   * @param token - 추가할 토큰 문자열
   */
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

  /**
   * 스트리밍 중인 메시지에 출처 정보 반영
   * - 'sources' 또는 'source_candidates' 이벤트 수신 시 호출
   * - ref에 저장하고 현재 스트리밍 메시지에 적용
   * - 렌더링은 트리거하지만 localStorage 저장은 하지 않음 (토큰 스트리밍 중이므로)
   *
   * @param sources - 백엔드 출처 목록
   */
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

  /**
   * 스트림 종료 후 최종 정리 작업
   * - result 이벤트를 받았으면 이미 완료됨 (중복 처리 방지)
   * - 받지 못했으면 현재까지 누적된 내용으로 최종 저장
   * - 토큰을 하나라도 받았으면 사이드바 갱신 트리거
   * - localStorage 저장 및 상태 초기화
   */
  const finalizeAfterStreamClose = useCallback(() => {
    if (isStopped()) {
      streamInFlightRef.current = false;
      return;
    }
    if (wasInterruptedRef.current) {
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
        sources: latestUiSourcesRef.current.length ? latestUiSourcesRef.current : (currentMessage.sources ?? []),
        detailed_tasks: currentMessage.detailed_tasks ?? [],
      };

      const finalData: ChatData = { ...prev, messages };
      localStorage.setItem(storageKeys.chat, JSON.stringify(finalData));
      return finalData;
    });

    if (hasStreamedTokenRef.current) {
      refreshRecentChatsNow();
    }

    setIsLoading(false);
    setShowPRSelection(false);
    setCurrentStep('router');
    streamingMessageIdRef.current = null;
    streamInFlightRef.current = false;
  }, [isStopped, refreshRecentChatsNow, storageKeys.chat]);

  /**
   * SSE 스트림 이벤트 핸들러
   * 백엔드에서 전송하는 다양한 이벤트 타입을 처리
   *
   * 이벤트 타입:
   * - status: RAG 처리 단계 업데이트 (router, rewrite, search 등)
   * - sources: 최종 인용 출처 (cited sources)
   * - source_candidates: 후보 출처 (non-cited sources)
   * - token/delta: 답변 토큰 스트리밍
   * - interrupt: PR 선택 요청
   * - result: 최종 답변 완료
   * - error: 스트림 에러
   * - ping: 연결 유지 (무시)
   *
   * @param event - SSE 이벤트 객체
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

        case 'delta': {
          hasStreamedTokenRef.current = true;
          appendTokenToStreamingMessage(event.delta);
          break;
        }

        // TODO: resume API 백엔드 구현 시 재활성
        case 'interrupt': {
          // 비활성: PR 선택 UI를 띄우지 않고 즉시 종료 상태로 전환 (무한 로딩 방지)
          console.warn('[useRagChat] interrupt event received but resume is disabled');
          setShowPRSelection(false);
          setPrList([]);
          setIsLoading(false);
          streamInFlightRef.current = false;
          setCurrentStep('router');
          abortStream();
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
      abortStream,
      appendAssistantAnswer,
      appendTokenToStreamingMessage,
      applyStreamingSources,
      isStopped,
      refreshRecentChatsNow,
    ],
  );

  /**
   * 새 질문 메시지 전송
   * - user 메시지를 즉시 추가하고 localStorage 저장
   * - 스트림 시작하여 답변 생성
   * - 중복 요청 방지 (isLoading 또는 streamInFlightRef 체크)
   *
   * @param message - 질문 내용
   */
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
      localStorage.setItem(storageKeys.chat, JSON.stringify(updated));
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

  /**
   * 기존 질문 수정 후 재전송
   * - 수정할 메시지 이후의 모든 메시지 제거
   * - 새 user 메시지로 교체
   * - 스트림 재시작하여 새 답변 생성
   *
   * @param messageId - 수정할 메시지 ID
   * @param newContent - 수정된 질문 내용
   */
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
      localStorage.setItem(storageKeys.chat, JSON.stringify(updated));

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

  // TODO: resume API 백엔드 구현 시 재활성
  // handlePRContinue는 현재 interrupt가 비활성이므로 호출되지 않음
  const handlePRContinue = useCallback(async (_selectedPrNumbers: number[]) => {
    console.warn('[useRagChat] handlePRContinue called but resume is disabled');
  }, []);

  /**
   * PR 다시 가져오기 (스트림 재시작)
   * - 현재 스트림 중단
   * - 마지막 user 질문으로 스트림 재시작
   * - PR 선택 화면에서 "다시 가져오기" 버튼 클릭 시 호출
   */
  const handlePRRefetch = useCallback(async () => {
    if (!chatData || streamInFlightRef.current) return;

    const lastUserMessage = [...chatData.messages].reverse().find((message) => message.role === 'user');
    const query = lastUserMessage?.content?.trim();
    if (!query) return;

    abortStream();
    beginAnswerLoading();

    try {
      await streamChat(query, handleStreamEvent);
      finalizeAfterStreamClose();
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        handleAbortError();
        return;
      }
      console.error('[useRagChat] handlePRRefetch error:', err);
      setIsError(true);
      setIsLoading(false);
      streamInFlightRef.current = false;
    }
  }, [
    abortStream,
    beginAnswerLoading,
    chatData,
    finalizeAfterStreamClose,
    handleAbortError,
    handleStreamEvent,
    streamChat,
  ]);

  /**
   * 스트림 중단 (사용자 요청)
   * - 사용자가 "중단" 버튼 클릭 시 호출
   * - 현재까지 받은 내용으로 메시지 저장
   * - 스트리밍 메시지가 없으면 빈 답변 추가
   */
  const handleStop = useCallback(() => {
    if (!isLoading) return;

    markStopped();
    abortStream();

    setIsLoading(false);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');

    if (!streamingMessageIdRef.current) {
      streamInFlightRef.current = false;
      appendAssistantAnswer('\n', [], []);
      return;
    }

    setChatData((prev) => {
      if (!prev) return prev;
      localStorage.setItem(storageKeys.chat, JSON.stringify(prev));
      return prev;
    });
    streamInFlightRef.current = false;
  }, [abortStream, appendAssistantAnswer, isLoading, markStopped, storageKeys.chat]);

  /**
   * 메시지의 피드백 상태 업데이트
   * 사용자가 피드백을 제출한 후 has_feedback을 true로 설정
   *
   * @param messageId - 업데이트할 메시지 ID
   */
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

  /**
   * 초기 질문이 있는데 user 메시지가 없는 경우 추가
   * initialQuery로 페이지 진입 시 첫 렌더링에서 실행
   */
  useEffect(() => {
    if (!effectiveInitialQuery) return;

    const hasUserMessage = chatData?.messages.some((message) => message.role === 'user') ?? false;
    if (hasUserMessage) return;

    queueMicrotask(() => {
      ensureInitialUserMessage(effectiveInitialQuery);
      setIsLoading(true);
    });
  }, [chatData, effectiveInitialQuery, ensureInitialUserMessage]);

  /**
   * 초기 질문에 대한 스트림 자동 시작
   * - initialQuery가 있고
   * - 스트림이 진행 중이 아니고
   * - assistant 답변이 없는 경우
   * → 자동으로 스트림 시작
   */
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
