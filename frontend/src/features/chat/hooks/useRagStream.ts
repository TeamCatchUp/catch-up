'use client';

import { useCallback, useEffect, useRef } from 'react';

import chatService from '@/features/chat/services/chatService';

interface UseRagStreamReturn {
  streamChat: (query: string, onEvent: (event: StreamEvent) => void) => Promise<void>;
  resumeStream: (
    payload: { pr_number: number; repo_name: string; owner: string }[],
    onEvent: (event: StreamEvent) => void,
  ) => Promise<void>;
  abortStream: () => void;
  markStopped: () => void;
  resetStopped: () => void;
  isStopped: () => boolean;
}

/**
 * useRagStream
 * SSE 스트림 연결/중단/정지 lifecycle 관리
 */
export const useRagStream = (sessionId: string): UseRagStreamReturn => {
  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);

  /** 스트림 중단 */
  const abortStream = useCallback(() => {
    if (abortRef.current) {
      console.log('[useRagStream] 스트림 중단');
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  /** 질문 스트림 전송 */
  const streamChat = useCallback(
    async (query: string, onEvent: (event: StreamEvent) => void) => {
      abortStream();
      const controller = new AbortController();
      abortRef.current = controller;
      await chatService.streamChat(query, sessionId, onEvent, controller.signal);
    },
    [sessionId, abortStream],
  );

  /** PR 선택 후 스트림 재개 */
  const resumeStream = useCallback(
    async (
      payload: { pr_number: number; repo_name: string; owner: string }[],
      onEvent: (event: StreamEvent) => void,
    ) => {
      abortStream();
      const controller = new AbortController();
      abortRef.current = controller;
      await chatService.resumeStream(sessionId, payload, onEvent, controller.signal);
    },
    [sessionId, abortStream],
  );

  /** 사용자가 응답 중지를 요청했음을 표시 */
  const markStopped = useCallback(() => {
    stoppedRef.current = true;
  }, []);

  /** 중지 상태 초기화 (새 스트림 시작 전) */
  const resetStopped = useCallback(() => {
    stoppedRef.current = false;
  }, []);

  /** 현재 중지 상태 확인 */
  const isStopped = useCallback(() => stoppedRef.current, []);

  // 언마운트 시 스트림 정리
  useEffect(() => {
    return () => {
      abortStream();
    };
  }, [abortStream]);

  return { streamChat, resumeStream, abortStream, markStopped, resetStopped, isStopped };
};
