'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { useInitialQueryBootstrap } from '@/features/chat/hooks/useRagChat.parts/initialQueryBootstrap';
import { useMessageActions } from '@/features/chat/hooks/useRagChat.parts/messageActions';
import { refreshRecentChats } from '@/features/chat/hooks/useRagChat.parts/refreshRecentChats';
import { useRagChatRefs } from '@/features/chat/hooks/useRagChat.parts/refs';
import {
  createEmptyChatData,
  loadLatestSessionPage,
  loadPreviousSessionPage,
  loadSessionChatData,
} from '@/features/chat/hooks/useRagChat.parts/sessionDataLoader';
import { useSessionLifecycle } from '@/features/chat/hooks/useRagChat.parts/sessionLifecycle';
import { useStreamProcessing } from '@/features/chat/hooks/useRagChat.parts/streamProcessing';
import type { UseRagChatOptions, UseRagChatReturn } from '@/features/chat/hooks/useRagChat.parts/types';
import { useRagStream } from '@/features/chat/hooks/useRagStream';
import type {
  ChatData,
  Message,
  PipelineQueryType,
  StepRow,
  StreamEvent,
} from '@/features/chat/types';
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
export const useRagChat = ({
  sessionId,
  repo,
  initialQuery,
  scrollToMessageId,
  toolFilters,
}: UseRagChatOptions): UseRagChatReturn => {
  // ---------------------------------------------------------------------------
  // External hooks/services
  // ---------------------------------------------------------------------------
  const router = useRouter();
  const queryClient = useQueryClient();
  const { streamChat: rawStreamChat, abortStream, markStopped, resetStopped, isStopped } = useRagStream();

  // toolFilters를 ref에 보관하여 wrapper의 useCallback deps를 안정적으로 유지
  const toolFiltersRef = useRef(toolFilters);
  toolFiltersRef.current = toolFilters;

  const streamChat = useCallback(
    (query: string, sid: string | undefined, onEvent: (event: StreamEvent) => void) =>
      rawStreamChat(query, sid, onEvent, toolFiltersRef.current),
    [rawStreamChat],
  );

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
  const [stepRows, setStepRows] = useState<StepRow[]>([]);
  const [pipelineQueryType, setPipelineQueryType] = useState<PipelineQueryType | null>(null);
  const [topic, setTopic] = useState<string | null>(null);
  const [pipelineReasoning, setPipelineReasoning] = useState<string | null>(null);

  // 모든 ref 기반 런타임 상태(세션 전환 가드, 스트림 플래그)를 전담 훅에서 관리
  const { sessionRefs, streamRefs, resetStreamStateRefs } = useRagChatRefs(resolvedSessionId);

  // ---------------------------------------------------------------------------
  // 역방향 무한 스크롤 pagination state
  // ---------------------------------------------------------------------------
  const [oldestLoadedPage, setOldestLoadedPage] = useState<number | null>(null);
  const [hasOlderMessages, setHasOlderMessages] = useState(false);
  const [isLoadingOlderMessages, setIsLoadingOlderMessages] = useState(false);
  const scrollToFullLoadRef = useRef<string | null>(null);

  const refreshRecentChatsNow = useCallback(() => {
    refreshRecentChats(queryClient);
  }, [queryClient]);

  // 비어 있는 ChatData를 만드는 helper (신규 세션/에러 fallback에서 사용)
  const buildEmptyChatData = useCallback(
    (targetSessionId: string) => createEmptyChatData(targetSessionId, repo, effectiveInitialQuery),
    [effectiveInitialQuery, repo],
  );

  // sessionDataLoader에 현재 컨텍스트(repo/initialQuery/queryClient)를 주입한 래퍼
  // scrollToMessageId 유무에 따라 전체 로드 vs 마지막 페이지만 로드 분기
  const loadSessionChatDataWithContext = useCallback(
    async (targetSessionId: string) => {
      if (scrollToMessageId) {
        // scrollTo 있으면 전체 로드 (대상 메시지가 어디 있을지 모르므로)
        const data = await loadSessionChatData({
          queryClient,
          sessionId: targetSessionId,
          repo,
          initialQuery: effectiveInitialQuery,
        });
        setOldestLoadedPage(1);
        setHasOlderMessages(false);
        return data;
      }

      // scrollTo 없으면 최신 페이지만 로드 (역방향 무한 스크롤)
      const result = await loadLatestSessionPage({
        queryClient,
        sessionId: targetSessionId,
        repo,
        initialQuery: effectiveInitialQuery,
      });
      setOldestLoadedPage(result.oldestLoadedPage);
      setHasOlderMessages(result.oldestLoadedPage > 1);
      return result.chatData;
    },
    [effectiveInitialQuery, queryClient, repo, scrollToMessageId],
  );

  // 역방향 무한 스크롤: 이전 페이지 로드
  const loadPreviousMessages = useCallback(async () => {
    const targetId = resolvedSessionId;
    if (!targetId || !oldestLoadedPage || oldestLoadedPage <= 1 || isLoadingOlderMessages) return;

    setIsLoadingOlderMessages(true);
    try {
      const prevPage = oldestLoadedPage - 1;
      const olderMessages = await loadPreviousSessionPage({
        queryClient,
        sessionId: targetId,
        page: prevPage,
      });

      setChatData((prev) => {
        if (!prev) return prev;
        return { ...prev, messages: [...olderMessages, ...prev.messages] };
      });

      setOldestLoadedPage(prevPage);
      setHasOlderMessages(prevPage > 1);
    } catch (err) {
      console.error('[useRagChat] loadPreviousMessages error:', err);
    } finally {
      setIsLoadingOlderMessages(false);
    }
  }, [resolvedSessionId, oldestLoadedPage, isLoadingOlderMessages, queryClient]);

  // 스트림 종료 후 서버 기준 최종 메시지로 1회 동기화
  const syncChatDataFromServer = useCallback(
    async (targetSessionId: string) => {
      if (!isValidSessionId(targetSessionId)) return;
      try {
        // 스트림 후 동기화는 전체 로드 (최신 상태 보장)
        const nextData = await loadSessionChatData({
          queryClient,
          sessionId: targetSessionId,
          repo,
          initialQuery: effectiveInitialQuery,
        });
        setChatData((prev) => {
          if (!prev) return nextData;

          // 서버 데이터의 assistant 메시지 중 sources가 비어있는 경우,
          // 스트리밍(prev)에서 수신한 sources를 보존한다. (서버 커밋 지연 대응)
          const mergedMessages = nextData.messages.map((serverMsg, idx) => {
            if (serverMsg.role !== 'assistant' || serverMsg.sources?.length) return serverMsg;

            const mergeWithPrev = (prevMsg: Message) => ({
              ...serverMsg,
              sources: prevMsg.sources,
            });

            // 같은 위치의 prev 메시지에서 sources 보존
            const prevByPos = prev.messages[idx];
            if (prevByPos?.role === 'assistant' && prevByPos.sources?.length) {
              return mergeWithPrev(prevByPos);
            }

            // content 기반 매칭 (trim 적용으로 공백 차이 허용)
            const trimmedContent = serverMsg.content.trim();
            const prevByContent = prev.messages.find(
              (m) => m.role === 'assistant' && m.content.trim() === trimmedContent && m.sources?.length,
            );
            if (prevByContent) {
              return mergeWithPrev(prevByContent);
            }

            return serverMsg;
          });

          // 서버 커밋 지연으로 아직 포함되지 않은 메시지 보존
          if (nextData.messages.length < prev.messages.length) {
            mergedMessages.push(...prev.messages.slice(nextData.messages.length));
          }

          return { ...nextData, messages: mergedMessages };
        });
        setOldestLoadedPage(1);
        setHasOlderMessages(false);
      } catch (err) {
        console.error('[useRagChat] syncChatDataFromServer error:', err);
      }
    },
    [effectiveInitialQuery, queryClient, repo],
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
      setStepRows,
      setPipelineQueryType,
      setTopic,
      setPipelineReasoning,
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
      setStepRows,
      setPipelineQueryType,
      setTopic,
      setPipelineReasoning,
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
    setStepRows,
    setPipelineQueryType,
    setTopic,
    setPipelineReasoning,
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
  // 같은 세션 내 scrollTo 네비게이션: 미로드 메시지 전체 로드
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!scrollToMessageId || !chatData || !resolvedSessionId || !isValidSessionId(resolvedSessionId)) return;
    if (!hasOlderMessages) return;
    if (scrollToFullLoadRef.current === scrollToMessageId) return;

    const targetId = `history_${scrollToMessageId}`;
    const targetExists = chatData.messages.some((m) => m.id === targetId);
    if (targetExists) return;

    scrollToFullLoadRef.current = scrollToMessageId;

    let cancelled = false;
    const loadAllForScrollTo = async () => {
      try {
        const data = await loadSessionChatData({
          queryClient,
          sessionId: resolvedSessionId,
          repo,
          initialQuery: effectiveInitialQuery,
        });
        if (cancelled) return;
        setChatData(data);
        setOldestLoadedPage(1);
        setHasOlderMessages(false);
      } catch (err) {
        if (!cancelled) console.error('[useRagChat] scrollTo full load error:', err);
      }
    };
    void loadAllForScrollTo();
    return () => {
      cancelled = true;
    };
  }, [
    scrollToMessageId,
    chatData,
    resolvedSessionId,
    hasOlderMessages,
    queryClient,
    repo,
    effectiveInitialQuery,
    setChatData,
  ]);

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------
  return {
    // 화면 데이터
    chatData,
    resolvedSessionId,
    isLoading,
    isError,
    stepRows,
    pipelineQueryType,
    topic,
    pipelineReasoning,

    // 사용자 액션
    sendMessage,
    submitEdit,
    handleStop,

    // 외부 연동(필요 시 강제 업데이트)
    setChatData,
    updateMessageFeedback,

    // 역방향 무한 스크롤
    hasOlderMessages,
    isLoadingOlderMessages,
    loadPreviousMessages,
  };
};

export default useRagChat;
