'use client';

import { useCallback, useEffect, useRef } from 'react';

import chatService from '@/features/chat/services/chatService';
import type { StreamEvent } from '@/features/chat/types';

/**
 * RAG 스트림 훅 반환 타입
 */
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
 * RAG SSE 스트림 관리 훅
 *
 * SSE 연결의 lifecycle을 관리하며 다음 기능을 제공:
 * - 질문 스트림 시작 (streamChat)
 * - PR 선택 후 스트림 재개 (resumeStream)
 * - 스트림 중단 (AbortController 기반)
 * - 사용자 중단 상태 추적 (stopped flag)
 *
 * @param sessionId - 현재 세션 ID
 * @returns 스트림 제어 함수들
 */
export const useRagStream = (sessionId: string): UseRagStreamReturn => {
  const abortRef = useRef<AbortController | null>(null);
  const stoppedRef = useRef(false);

  /**
   * 스트림 중단
   * AbortController를 사용하여 fetch 요청 취소
   */
  const abortStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  /**
   * 질문 스트림 전송
   * - 새 질문에 대한 SSE 스트림 시작
   * - 이미 진행 중인 스트림이 있으면 무시
   * - 완료 또는 에러 시 자동으로 AbortController 정리
   *
   * @param query - 질문 내용
   * @param onEvent - 스트림 이벤트 핸들러
   */
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

  /**
   * PR 선택 후 스트림 재개
   * - interrupt 이벤트 이후 사용자가 PR 선택 완료 시 호출
   * - 선택된 PR 정보를 백엔드에 전송하고 답변 생성 재개
   *
   * @param payload - 선택된 PR 목록 (pr_number, repo_name, owner)
   * @param onEvent - 스트림 이벤트 핸들러
   */
  const resumeStream = useCallback(
    async (
      payload: { pr_number: number; repo_name: string; owner: string }[],
      onEvent: (event: StreamEvent) => void,
    ) => {
      const activeController = abortRef.current;
      if (activeController && !activeController.signal.aborted) return;
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await chatService.resumeStream(sessionId, payload, onEvent, controller.signal);
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [sessionId],
  );

  /**
   * 사용자가 응답 중지를 요청했음을 표시
   * handleStop 호출 시 설정되며, 이후 이벤트 처리를 스킵하는 데 사용
   */
  const markStopped = useCallback(() => {
    stoppedRef.current = true;
  }, []);

  /**
   * 중지 상태 초기화
   * 새 스트림 시작 전에 호출하여 stopped 플래그 리셋
   */
  const resetStopped = useCallback(() => {
    stoppedRef.current = false;
  }, []);

  /**
   * 현재 중지 상태 확인
   * @returns 사용자가 중단 요청했는지 여부
   */
  const isStopped = useCallback(() => stoppedRef.current, []);

  /**
   * 컴포넌트 언마운트 시 스트림 정리
   * 진행 중인 스트림이 있으면 자동으로 중단
   */
  useEffect(() => {
    return () => {
      abortStream();
    };
  }, [abortStream]);

  return { streamChat, resumeStream, abortStream, markStopped, resetStopped, isStopped };
};
