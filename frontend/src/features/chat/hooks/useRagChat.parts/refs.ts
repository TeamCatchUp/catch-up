import { useCallback, useEffect, useMemo, useRef } from 'react';

import type { ChatSource, SourceResponse } from '@/features/chat/types';

import type { ActiveStreamQuestion, SessionGuardRefs, StreamRuntimeRefs } from './types';

interface UseRagChatRefsReturn {
  // 세션 전환 제어 ref 묶음
  sessionRefs: SessionGuardRefs;
  // 스트림 처리 ref 묶음
  streamRefs: StreamRuntimeRefs;
  // 스트림 시작 전에 매번 초기화해야 하는 ref들만 리셋
  resetStreamStateRefs: () => void;
}

/**
 * useRagChat 내부에서 쓰는 ref들을 한 곳에서 생성/관리한다.
 * - 렌더링과 무관한 스트림 제어 상태를 ref로 유지
 * - session guard/ref 집합을 분리해 다른 part 훅에 주입하기 쉽게 만듦
 */
export const useRagChatRefs = (resolvedSessionId: string | undefined): UseRagChatRefsReturn => {
  // ------------------------------
  // Session guard refs
  // ------------------------------
  // useEffect가 session 변경 때마다 다시 돌더라도,
  // replace/hydrate 중복 실행을 막기 위해 렌더링과 무관한 플래그를 ref로 유지한다.
  const syncedSessionRef = useRef<string | null>(null);
  const sessionSyncGuardRef = useRef<{ from: string; to: string } | null>(null);
  const pendingReplaceSessionIdRef = useRef<string | null>(null);
  const hasPlaceholderReplacedRef = useRef(false);
  const canReplacePlaceholderRef = useRef(false);

  // ------------------------------
  // Stream runtime refs
  // ------------------------------
  // token/result 이벤트는 state 업데이트보다 훨씬 자주/빠르게 들어올 수 있다.
  // 이벤트 핸들러가 stale state에 의존하지 않게 ref를 단일 source of truth로 사용한다.
  const streamingMessageIdRef = useRef<string | null>(null);
  const hasStreamedTokenRef = useRef(false);

  const latestSourcesRef = useRef<SourceResponse[]>([]);
  const latestUiSourcesRef = useRef<ChatSource[]>([]);
  const streamInFlightRef = useRef(false);
  const hasAttemptedInitialStreamRef = useRef(false);
  const resolvedSessionIdRef = useRef<string | undefined>(resolvedSessionId);
  const activeQuestionRef = useRef<ActiveStreamQuestion | null>(null);

  // finalize 시점에 stale closure로 예전 sessionId를 보는 문제를 막기 위해
  // 항상 최신 resolvedSessionId를 ref에 동기화한다.
  useEffect(() => {
    resolvedSessionIdRef.current = resolvedSessionId;
  }, [resolvedSessionId]);

  // "한 번의 스트림 요청" 수명주기가 끝날 때마다 초기화해야 하는 ref들만 리셋한다.
  // session 전환 가드(ref)는 여기서 초기화하지 않는다.
  const resetStreamStateRefs = useCallback(() => {
    streamingMessageIdRef.current = null;
    hasStreamedTokenRef.current = false;
    latestSourcesRef.current = [];
    latestUiSourcesRef.current = [];
  }, []);

  // 객체 자체가 매 렌더마다 바뀌지 않도록 memoized container로 감싼다.
  // 각 part 훅에서 의존성 배열이 불필요하게 흔들리는 것을 방지한다.
  const sessionRefs = useMemo<SessionGuardRefs>(
    () => ({
      syncedSessionRef,
      sessionSyncGuardRef,
      pendingReplaceSessionIdRef,
      hasPlaceholderReplacedRef,
      canReplacePlaceholderRef,
    }),
    [],
  );

  // stream refs도 동일하게 stable reference를 보장한다.
  const streamRefs = useMemo<StreamRuntimeRefs>(
    () => ({
      streamingMessageIdRef,
      hasStreamedTokenRef,
      latestSourcesRef,
      latestUiSourcesRef,
      streamInFlightRef,
      hasAttemptedInitialStreamRef,
      resolvedSessionIdRef,
      activeQuestionRef,
    }),
    [],
  );

  return {
    sessionRefs,
    streamRefs,
    resetStreamStateRefs,
  };
};
