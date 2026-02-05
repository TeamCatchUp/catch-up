/**
 * useRagPagination
 * Q&A 페이지 전환 및 localStorage 동기화
 */

'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { extractQAPairs, findQAPairIndexByQuery, type QAPair } from '@/util/ragAnswer/chat';
import { ANIMATION_CONFIG, getStorageKeys } from '@/constants/ragAnswer/config';

interface UseRagPaginationOptions {
  sessionId: string;
  messages: Message[];
  isLoading: boolean;
}

interface UseRagPaginationReturn {
  // State
  currentPage: number;
  slideDirection: 'up' | 'down' | null;
  qaPairs: QAPair[];
  currentQA: QAPair | undefined;

  // Actions
  setCurrentPage: React.Dispatch<React.SetStateAction<number>>;
  setSlideDirection: React.Dispatch<React.SetStateAction<'up' | 'down' | null>>;
  goToPage: (page: number) => void;
  goToNewPage: (newPageIndex: number) => void;
  goToQuestion: (query: string) => void;
}

export const useRagPagination = ({
  sessionId,
  messages,
  isLoading,
}: UseRagPaginationOptions): UseRagPaginationReturn => {
  // localStorage 키
  const storageKeys = useMemo(() => getStorageKeys(sessionId), [sessionId]);

  // 페이지 상태 (localStorage에서 초기값 복원)
  const [currentPage, setCurrentPage] = useState<number>(() => {
    if (typeof window === 'undefined') return 0;
    const saved = localStorage.getItem(storageKeys.page);
    const n = saved ? Number(saved) : 0;
    return Number.isFinite(n) ? n : 0;
  });

  // 슬라이드 애니메이션 방향
  const [slideDirection, setSlideDirection] = useState<'up' | 'down' | null>(null);

  // Q&A 쌍 추출
  const qaPairs = useMemo(() => extractQAPairs(messages), [messages]);

  // 현재 Q&A
  const currentQA = qaPairs[currentPage];

  /** localStorage 동기화 */
  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(storageKeys.page, String(currentPage));
  }, [storageKeys.page, currentPage]);

  /** 페이지 유효성 검증 */
  useEffect(() => {
    if (qaPairs.length > 0 && currentPage >= qaPairs.length) {
      setCurrentPage(qaPairs.length - 1);
    }
  }, [qaPairs.length, currentPage]);

  /** 특정 페이지로 이동 (애니메이션 포함) */
  const goToPage = useCallback(
    (targetPage: number) => {
      if (isLoading || targetPage === currentPage) return;
      if (targetPage < 0 || targetPage >= qaPairs.length) return;

      setSlideDirection(targetPage > currentPage ? 'up' : 'down');

      setTimeout(() => {
        setCurrentPage(targetPage);
        setSlideDirection(null);
      }, ANIMATION_CONFIG.SLIDE_DURATION_MS);
    },
    [isLoading, currentPage, qaPairs.length],
  );

  /** 새 페이지로 이동 (새 질문 전송 시) */
  const goToNewPage = useCallback(
    (newPageIndex: number) => {
      setSlideDirection('up');

      setTimeout(() => {
        setCurrentPage(newPageIndex);
        setSlideDirection(null);
      }, ANIMATION_CONFIG.SLIDE_DURATION_MS);
    },
    [],
  );

  /** 질문 내용으로 페이지 찾아 이동 */
  const goToQuestion = useCallback(
    (query: string) => {
      const idx = findQAPairIndexByQuery(qaPairs, query);
      if (idx === -1) return;

      setSlideDirection(idx > currentPage ? 'up' : 'down');

      setTimeout(() => {
        setCurrentPage(idx);
        setSlideDirection(null);
      }, ANIMATION_CONFIG.SLIDE_DURATION_MS);
    },
    [qaPairs, currentPage],
  );

  return {
    currentPage,
    slideDirection,
    qaPairs,
    currentQA,
    setCurrentPage,
    setSlideDirection,
    goToPage,
    goToNewPage,
    goToQuestion,
  };
};

export default useRagPagination;
