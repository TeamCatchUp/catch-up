'use client';

import { useCallback, useEffect, useRef } from 'react';

import chatService from '@/features/chat/services/chatService';
import type { StreamEvent } from '@/features/chat/types';

interface UseRagStreamReturn {
  streamChat: (query: string, onEvent: (event: StreamEvent) => void) => Promise<void>;
  abortStream: () => void;
  markStopped: () => void;
  resetStopped: () => void;
  isStopped: () => boolean;
}

/**
 * RAG SSE 스트림 관리 훅
 *
 * SSE 연결의 lifecycle을 관리하며 다음 기능을 제공:
 * - 질문 스트림 시작 (streamChat)
 * - 스트림 중단 (AbortController 기반)
 * - 사용자 중단 상태 추적 (stopped flag)
 */
export const useRagStream = (sessionId: string): UseRagStreamReturn => {
  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);

  const abortStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const streamChat = useCallback(
    async (query: string, onEvent: (event: StreamEvent) => void) => {
      const activeController = abortRef.current;
      if (activeController && !activeController.signal.aborted) return;
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await chatService.streamChat(query, sessionId, onEvent, controller.signal);
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [sessionId],
  );

  const markStopped = useCallback(() => {
    stoppedRef.current = true;
  }, []);

  const resetStopped = useCallback(() => {
    stoppedRef.current = false;
  }, []);

  const isStopped = useCallback(() => stoppedRef.current, []);

  useEffect(() => {
    return () => {
      abortStream();
    };
  }, [abortStream]);

  return { streamChat, abortStream, markStopped, resetStopped, isStopped };
};
