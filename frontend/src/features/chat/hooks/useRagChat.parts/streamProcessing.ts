import { useCallback } from 'react';

import { NODE_TO_UI_STEP } from '@/features/chat/constants/config';
import {
  appendStreamingToken,
  updateStreamingSources,
} from '@/features/chat/hooks/useRagChat.parts/streamMessageUpdater';
import type { SourceResponse, StreamEvent } from '@/features/chat/types';
import { normalizeStreamSources } from '@/features/chat/utils/normalize/normalizeRagSources';
import { normalizeRelatedJiraIssues } from '@/features/chat/utils/normalize/normalizeRelatedJiraIssues';

import type { ChatStateSetters, SessionGuardRefs, StreamRuntimeRefs } from './types';

interface UseStreamProcessingParams {
  // 첫 질문(q) 컨텍스트
  effectiveInitialQuery: string | null;

  // 스트림 제어 함수
  resetStopped: () => void;
  isStopped: () => boolean;
  resetStreamStateRefs: () => void;

  // 종료 후 동기화/부수효과
  syncChatDataFromServer: (sessionId: string) => Promise<void>;
  refreshRecentChatsNow: () => void;
  resolveSessionIdFromStream: (streamSessionId?: string) => void;

  // 상태 세터 + ref
  stateSetters: ChatStateSetters;
  sessionRefs: SessionGuardRefs;
  streamRefs: StreamRuntimeRefs;
}

interface UseStreamProcessingReturn {
  beginAnswerLoading: () => void;
  ensureInitialUserMessage: (query: string) => void;
  handleAbortError: () => void;
  appendAssistantAnswer: (
    answer?: string,
    sources?: SourceResponse[],
    relatedJiraIssues?: SourceResponse[],
    chatHistoryId?: string,
    hasFeedback?: boolean,
  ) => void;
  finalizeAfterStreamClose: () => Promise<void>;
  handleStreamEvent: (event: StreamEvent) => void;
}

/**
 * 스트리밍 도중 발생하는 이벤트를 UI 상태로 반영하는 로직 묶음.
 * useRagChat 본문에서 가장 큰 분기를 분리해 가독성을 높인다.
 */
export const useStreamProcessing = ({
  effectiveInitialQuery,
  resetStopped,
  isStopped,
  resetStreamStateRefs,
  syncChatDataFromServer,
  refreshRecentChatsNow,
  resolveSessionIdFromStream,
  stateSetters,
  sessionRefs,
  streamRefs,
}: UseStreamProcessingParams): UseStreamProcessingReturn => {
  // ---------------------------------------------------------------------------
  // Shared setters/refs
  // ---------------------------------------------------------------------------
  const { setChatData, setIsLoading, setIsError, setCurrentStep } = stateSetters;
  const { canReplacePlaceholderRef } = sessionRefs;
  const {
    streamingMessageIdRef,
    hasStreamedTokenRef,
    hasResultEventRef,
    latestSourcesRef,
    latestUiSourcesRef,
    streamInFlightRef,
    resolvedSessionIdRef,
  } = streamRefs;

  // ---------------------------------------------------------------------------
  // Stream lifecycle helpers
  // ---------------------------------------------------------------------------
  /**
   * "답변 생성 시작" 공통 처리
   * - stopped flag 초기화
   * - 이전 스트림 잔여 ref 초기화
   * - 로딩/단계 상태 시작값 세팅
   */
  const beginAnswerLoading = useCallback(() => {
    resetStopped();
    resetStreamStateRefs();
    streamInFlightRef.current = true;
    canReplacePlaceholderRef.current = false;
    setIsLoading(true);
    setIsError(false);
    setCurrentStep('router');
  }, [canReplacePlaceholderRef, resetStopped, resetStreamStateRefs, setCurrentStep, setIsError, setIsLoading, streamInFlightRef]);

  /**
   * 첫 질문 자동 실행 시, user 메시지가 아직 없으면 1회 생성
   * - token이 먼저 와도 user/assistant 페어가 깨지지 않게 보정
   */
  const ensureInitialUserMessage = useCallback(
    (query: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;

      setChatData((prev) => {
        if (!prev) return prev;

        const hasUser = prev.messages.some((message) => message.role === 'user');
        if (hasUser) return prev;

        return {
          ...prev,
          title: prev.title || trimmed,
          messages: [
            ...prev.messages,
            {
              id: crypto.randomUUID(),
              role: 'user',
              content: trimmed,
              timestamp: new Date().toISOString(),
            },
          ],
        };
      });
    },
    [setChatData],
  );

  const handleAbortError = useCallback(() => {
    streamInFlightRef.current = false;

    if (isStopped()) return;

    setIsLoading(false);
    setCurrentStep('router');
  }, [isStopped, setCurrentStep, setIsLoading, streamInFlightRef]);

  /**
   * result 이벤트를 assistant 메시지에 반영
   * - 기존 streaming 메시지가 있으면 update
   * - 없으면 새 assistant 메시지 append
   * - latestSourcesRef/latestUiSourcesRef도 함께 갱신
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

        const uiSources = normalizeStreamSources(sources);
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

        return {
          ...prev,
          messages: [
            ...prev.messages,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: answer,
              sources: uiSources,
              detailed_tasks: detailedTasks,
              timestamp: new Date().toISOString(),
              chat_history_id: chatHistoryId,
              has_feedback: hasFeedback,
            },
          ],
        };
      });
      streamingMessageIdRef.current = null;
    },
    [latestSourcesRef, latestUiSourcesRef, setChatData, streamingMessageIdRef],
  );

  /**
   * token 이벤트를 현재 streaming 메시지에 append
   * - 메시지가 없으면 updater가 자동으로 assistant 메시지를 생성
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
    [effectiveInitialQuery, latestUiSourcesRef, setChatData, streamingMessageIdRef],
  );

  /**
   * sources/source_candidates 이벤트를 현재 streaming 메시지에 반영
   */
  const applyStreamingSources = useCallback(
    (sources: SourceResponse[] = []) => {
      latestSourcesRef.current = sources;
      latestUiSourcesRef.current = normalizeStreamSources(sources);

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
    },
    [latestSourcesRef, latestUiSourcesRef, setChatData, streamingMessageIdRef],
  );

  /**
   * 스트림 종료 후 후처리
   * - stopped면 조용히 종료
   * - 정상 종료면 서버 기준 메시지 재동기화
   * - placeholder replace 허용 플래그를 이 시점에만 켠다
   */
  const finalizeAfterStreamClose = useCallback(async () => {
    if (isStopped()) {
      streamInFlightRef.current = false;
      return;
    }
    canReplacePlaceholderRef.current = true;

    const targetSessionId = resolvedSessionIdRef.current;

    if (hasResultEventRef.current) {
      // 로딩 해제를 먼저 수행 → 소스 즉시 표시
      streamingMessageIdRef.current = null;
      setIsLoading(false);
      setCurrentStep('router');
      streamInFlightRef.current = false;

      // 서버 동기화는 백그라운드 (chat_history_id 등 보정용)
      if (targetSessionId) {
        syncChatDataFromServer(targetSessionId);
      }
      return;
    }

    // result 이벤트 없이 토큰만 온 경우 (백엔드 비정상 종료)
    setIsLoading(false);
    setCurrentStep('router');
    streamingMessageIdRef.current = null;
    streamInFlightRef.current = false;

    if (hasStreamedTokenRef.current) {
      if (targetSessionId) {
        syncChatDataFromServer(targetSessionId);
        refreshRecentChatsNow();
      }
      return;
    }

    // status만 수신한 뒤 종료된 경우(예: 백엔드에서 예외 후 스트림 종료) 빈 화면 대신 에러를 노출한다.
    setIsError(true);
  }, [
    canReplacePlaceholderRef,
    hasResultEventRef,
    hasStreamedTokenRef,
    isStopped,
    refreshRecentChatsNow,
    resolvedSessionIdRef,
    setCurrentStep,
    setIsError,
    setIsLoading,
    streamInFlightRef,
    streamingMessageIdRef,
    syncChatDataFromServer,
  ]);

  // ---------------------------------------------------------------------------
  // SSE event router
  // ---------------------------------------------------------------------------
  /**
   * SSE 이벤트 라우터
   * - status: 단계(progress) 업데이트
   * - token/sources/result: 메시지 내용 업데이트
   * - error: 에러 플래그 전환
   */
  const handleStreamEvent = useCallback(
    (event: StreamEvent) => {
      // 가능한 가장 이른 시점에 session_id를 흡수해 stale session 문제를 줄인다.
      if ('session_id' in event) {
        resolveSessionIdFromStream(event.session_id);
      }
      if (isStopped()) return;

      switch (event.type) {
        case 'status': {
          // 백엔드 node명을 UI 단계로 매핑
          const mappedStep = NODE_TO_UI_STEP[event.node];
          if (mappedStep === null || mappedStep === undefined) return;
          setCurrentStep(mappedStep);
          break;
        }
        case 'sources': {
          // 최종 답변 이전에 전달되는 후보/중간 sources
          applyStreamingSources(event.sources ?? []);
          break;
        }
        case 'source_candidates': {
          // 백엔드 구현에 따라 별도 타입으로 전달되는 sources 후보군
          applyStreamingSources(event.sources ?? []);
          break;
        }
        case 'token': {
          // 토큰 스트리밍 본문 누적
          hasStreamedTokenRef.current = true;
          appendTokenToStreamingMessage(event.token);
          break;
        }
        case 'result': {
          // 최종 답변/출처/피드백 가능 여부를 확정 반영
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
          // 서버가 명시적으로 에러 이벤트를 내려준 경우
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
      hasResultEventRef,
      hasStreamedTokenRef,
      isStopped,
      refreshRecentChatsNow,
      resolveSessionIdFromStream,
      setCurrentStep,
      setIsError,
      setIsLoading,
      streamInFlightRef,
    ],
  );

  return {
    beginAnswerLoading,
    ensureInitialUserMessage,
    handleAbortError,
    appendAssistantAnswer,
    finalizeAfterStreamClose,
    handleStreamEvent,
  };
};
