'use client';

import { useCallback, useEffect, useRef } from 'react';

import chatService from '@/features/chat/services/chatService';
import type { SseStreamEventEnvelopeApi, StreamEvent } from '@/features/chat/types';

interface UseRagStreamReturn {
  streamChat: (
    query: string,
    sessionId: string | undefined,
    onEvent: (event: StreamEvent) => void,
    toolFilters?: string[],
  ) => Promise<void>;
  reconnectChatStream: (sessionId: string, onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void) => Promise<void>;
  cancelGeneration: (sessionId: string) => Promise<void>;
  abortStream: () => void;
  markStopped: () => void;
  resetStopped: () => void;
  isStopped: () => boolean;
}

/**
 * RAG SSE 스트림 관리 훅
 *
 * SSE 연결의 lifecycle을 관리하며 다음 기능을 제공:
 * - 질문 스트림 시작 (streamChat, sessionId 선택 전달)
 * - 스트림 중단 (AbortController 기반)
 * - 사용자 중단 상태 추적 (stopped flag)
 */
export const useRagStream = (): UseRagStreamReturn => {
  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);

  const abortStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const streamChat = useCallback(
    async (
      query: string,
      sessionId: string | undefined,
      onEvent: (event: StreamEvent) => void,
      toolFilters?: string[],
    ) => {
      const activeController = abortRef.current;
      if (activeController && !activeController.signal.aborted) return;
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await chatService.streamChat(query, sessionId, onEvent, controller.signal, toolFilters);
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [],
  );

  const reconnectChatStream = useCallback(
    async (sessionId: string, onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void) => {
      const activeController = abortRef.current;
      if (activeController && !activeController.signal.aborted) return;
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await chatService.reconnectChatStream(sessionId, onEnvelope, controller.signal);
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [],
  );

  const cancelGeneration = useCallback(async (sessionId: string) => {
    await chatService.cancelGeneration(sessionId);
  }, []);

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

  return { streamChat, reconnectChatStream, cancelGeneration, abortStream, markStopped, resetStopped, isStopped };
};
