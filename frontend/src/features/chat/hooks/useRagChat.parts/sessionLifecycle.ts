import type { Dispatch, SetStateAction } from 'react';
import { useCallback, useEffect } from 'react';
import type { QueryClient } from '@tanstack/react-query';

import type { ChatData } from '@/features/chat/types';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import { isValidSessionId } from '@/shared/utils/sessionId';

import { isSessionMessagesNotFoundError, MESSAGE_PAGE_SIZE } from './sessionDataLoader';
import type { ChatStateSetters, SessionGuardRefs, StreamRuntimeRefs } from './types';

interface UseSessionLifecycleParams {
  // 현재 URL 기준 세션 상태
  sessionId: string;
  isPlaceholderSession: boolean;
  isLoading: boolean;
  chatData: ChatData | null;
  provisionalSessionId: string | undefined;
  setProvisionalSessionId: Dispatch<SetStateAction<string | undefined>>;
  resolvedSessionId: string | undefined;

  // URL 질의 파라미터 기반 첫 질문
  initialQueryFromUrl: string | null;
  effectiveInitialQuery: string | null;

  // 외부 의존성
  queryClient: QueryClient;
  router: { replace: (href: string) => void };
  abortStream: () => void;
  resetStreamStateRefs: () => void;

  // 데이터 로더/상태 세터
  buildEmptyChatData: (sessionId: string) => ChatData;
  loadSessionChatDataWithContext: (sessionId: string) => Promise<ChatData>;
  stateSetters: ChatStateSetters;

  // ref 묶음
  sessionRefs: SessionGuardRefs;
  streamRefs: StreamRuntimeRefs;
}

interface UseSessionLifecycleReturn {
  resolveSessionIdFromStream: (streamSessionId?: string) => void;
  clearInitialQueryParam: () => void;
}

/**
 * 세션 경로 전환 관련 lifecycle을 한 곳에서 관리한다.
 * - /chat/{sessionId} 진입 시 hydrate
 * - /chat/new -> /chat/{resolvedSessionId} replace 제어
 * - URL의 초기 q 파라미터 제거
 */
export const useSessionLifecycle = ({
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
  stateSetters,
  sessionRefs,
  streamRefs,
}: UseSessionLifecycleParams): UseSessionLifecycleReturn => {
  // ---------------------------------------------------------------------------
  // Shared setters/refs
  // ---------------------------------------------------------------------------
  const { setChatData, setIsLoading, setIsError, setCurrentStep } = stateSetters;
  const { syncedSessionRef, sessionSyncGuardRef, pendingReplaceSessionIdRef, hasPlaceholderReplacedRef, canReplacePlaceholderRef } =
    sessionRefs;
  const { streamInFlightRef, hasAttemptedInitialStreamRef } = streamRefs;

  /**
   * SSE 이벤트에 `session_id`가 포함되어 들어오면 세션을 확정한다.
   *
   * 중요:
   * - placeholder(`/chat/new`)일 때만 pending replace를 설정
   * - 이미 같은 session이면 무시
   */
  const resolveSessionIdFromStream = useCallback(
    (streamSessionId?: string) => {
      if (!streamSessionId) return;
      if (resolvedSessionId === streamSessionId) return;

      setProvisionalSessionId(streamSessionId);

      if (!isPlaceholderSession) return;
      pendingReplaceSessionIdRef.current = streamSessionId;
    },
    [isPlaceholderSession, pendingReplaceSessionIdRef, resolvedSessionId, setProvisionalSessionId],
  );

  // ---------------------------------------------------------------------------
  // Session hydration effect
  // ---------------------------------------------------------------------------
  /**
   * sessionId 변경 시 실행되는 메인 lifecycle effect.
   *
   * 처리 순서:
   * 1) 이전 스트림 상태 정리
   * 2) 세션 유효성 확인
   * 3) 신규 UUID+q 초기 진입이면 hydrate 스킵
   * 4) 기존 세션이면 서버 메시지 hydrate
   */
  useEffect(() => {
    const previousSessionId = syncedSessionRef.current;
    if (previousSessionId === sessionId) {
      // Dev StrictMode에서는 mount effect가 "실행 -> cleanup -> 재실행"된다.
      // 첫 실행에서 hydrate가 cleanup으로 취소되면, 같은 sessionId라도 1회 재시도해야 로딩 고착을 막을 수 있다.
      // 따라서 "아직 hydrate 결과가 없는 상태(chatData=null && isLoading=true)"일 때만 계속 진행한다.
      const needsStrictModeHydrationRetry = chatData === null && isLoading;
      if (!needsStrictModeHydrationRetry) return;
    }

    // replace 직후 "한 번만 허용"해야 하는 경로 전환은 guard로 통과시킨다.
    const guard = sessionSyncGuardRef.current;
    if (guard && guard.from === previousSessionId && guard.to === sessionId) {
      syncedSessionRef.current = sessionId;
      sessionSyncGuardRef.current = null;
      pendingReplaceSessionIdRef.current = null;
      hasPlaceholderReplacedRef.current = false;
      return;
    }

    // 새 세션 진입 시작: 모든 스트림 관련 런타임 상태를 초기화
    syncedSessionRef.current = sessionId;

    streamInFlightRef.current = false;
    hasAttemptedInitialStreamRef.current = false;
    canReplacePlaceholderRef.current = false;
    hasPlaceholderReplacedRef.current = false;
    resetStreamStateRefs();
    abortStream();

    setIsError(false);
    setCurrentStep('router');

    // UUID가 아닌 placeholder/잘못된 세션은 빈 상태만 세팅
    if (!isValidSessionId(sessionId)) {
      setChatData(buildEmptyChatData(sessionId));
      setIsLoading(false);
      return;
    }

    // 프론트 생성 UUID로 첫 진입(+q)한 신규 세션은 room이 아직 없어 messages API가 404가 된다.
    // 이 경우 초기 hydrate를 건너뛰고, 초기 stream 이후 서버 동기화로 메시지를 채운다.
    const hasCachedPageOne = Boolean(
      queryClient.getQueryData(chatQueries.sessionMessages(sessionId, 1, MESSAGE_PAGE_SIZE).queryKey),
    );
    if (effectiveInitialQuery && !hasCachedPageOne) {
      setChatData(buildEmptyChatData(sessionId));
      setIsLoading(false);
      return;
    }

    // 여기부터는 "실제 서버 히스토리 hydrate" 경로
    let cancelled = false;

    const hydrateSession = async () => {
      setIsLoading(true);
      setChatData(null);

      try {
        const nextData = await loadSessionChatDataWithContext(sessionId);
        if (cancelled) return;
        setChatData(nextData);
      } catch (err) {
        if (cancelled) return;
        if (effectiveInitialQuery && isSessionMessagesNotFoundError(err)) {
          // 신규 세션 생성 직전 404는 정상 흐름
          setIsError(false);
          setChatData(buildEmptyChatData(sessionId));
        } else {
          console.error('[useRagChat] loadSessionChatData error:', err);
          setIsError(true);
          setChatData(buildEmptyChatData(sessionId));
        }
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
  }, [
    abortStream,
    buildEmptyChatData,
    canReplacePlaceholderRef,
    chatData,
    effectiveInitialQuery,
    hasAttemptedInitialStreamRef,
    hasPlaceholderReplacedRef,
    isLoading,
    loadSessionChatDataWithContext,
    pendingReplaceSessionIdRef,
    queryClient,
    resetStreamStateRefs,
    sessionId,
    sessionSyncGuardRef,
    setChatData,
    setCurrentStep,
    setIsError,
    setIsLoading,
    streamInFlightRef,
    syncedSessionRef,
  ]);

  // ---------------------------------------------------------------------------
  // Placeholder URL replace effect (/chat/new -> /chat/{resolvedId})
  // ---------------------------------------------------------------------------
  /**
   * placeholder 세션 URL 치환:
   * - 스트림이 정상 종료되어 `canReplacePlaceholderRef`가 true인 경우에만 수행
   * - `/chat/new` -> `/chat/{resolvedId}` 1회 replace
   */
  useEffect(() => {
    if (!isPlaceholderSession) return;
    if (!provisionalSessionId) return;
    if (isLoading) return;
    if (!canReplacePlaceholderRef.current) return;
    if (hasPlaceholderReplacedRef.current) return;

    hasPlaceholderReplacedRef.current = true;
    sessionSyncGuardRef.current = { from: sessionId, to: provisionalSessionId };
    pendingReplaceSessionIdRef.current = provisionalSessionId;

    const nextUrl = (() => {
      if (typeof window === 'undefined') return `/chat/${provisionalSessionId}`;
      // q는 1회 부트스트랩 값이라 최종 URL에서는 제거
      const params = new URLSearchParams(window.location.search);
      params.delete('q');
      const queryString = params.toString();
      return queryString ? `/chat/${provisionalSessionId}?${queryString}` : `/chat/${provisionalSessionId}`;
    })();

    router.replace(nextUrl);
  }, [
    canReplacePlaceholderRef,
    hasPlaceholderReplacedRef,
    isLoading,
    isPlaceholderSession,
    pendingReplaceSessionIdRef,
    provisionalSessionId,
    router,
    sessionId,
    sessionSyncGuardRef,
  ]);

  // ---------------------------------------------------------------------------
  // URL query cleanup helper
  // ---------------------------------------------------------------------------
  /**
   * 첫 질문 부트스트랩이 끝난 뒤 URL에서 `?q`를 제거한다.
   * - 같은 질문으로 자동 스트림이 재실행되는 것을 방지
   */
  const clearInitialQueryParam = useCallback(() => {
    if (!initialQueryFromUrl) return;
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    if (!params.has('q')) return;

    params.delete('q');
    const queryString = params.toString();
    const nextUrl = queryString ? `/chat/${sessionId}?${queryString}` : `/chat/${sessionId}`;
    router.replace(nextUrl);
  }, [initialQueryFromUrl, router, sessionId]);

  return {
    resolveSessionIdFromStream,
    clearInitialQueryParam,
  };
};
