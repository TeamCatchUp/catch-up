/**
 * useRagScroll
 * 연속 스크롤 기반 Q&A 렌더링 + Intersection Observer 사이드바 연동
 * useRagPagination 대체
 */

'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { extractQAPairs, type QAPair } from '@/features/chat/utils/chat';

interface UseRagScrollOptions {
  messages: Message[];
}

interface UseRagScrollReturn {
  qaPairs: QAPair[];
  qaRefs: React.MutableRefObject<Map<number, HTMLDivElement | null>>;
  scrollToLatest: () => void;
  activePairIndex: number;
}

export const useRagScroll = ({ messages }: UseRagScrollOptions): UseRagScrollReturn => {
  const qaPairs = useMemo(() => extractQAPairs(messages), [messages]);
  const qaRefs = useRef<Map<number, HTMLDivElement | null>>(new Map());
  const [activePairIndex, setActivePairIndex] = useState(0);
  const pendingScrollRef = useRef(false);

  // Intersection Observer: 뷰포트에 보이는 QA 감지 → 사이드바 연동
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        // 가장 많이 보이는(intersectionRatio 가장 큰) QA를 active로
        let bestIdx = -1;
        let bestRatio = 0;

        for (const entry of entries) {
          if (!entry.isIntersecting) continue;

          const idx = Number(entry.target.getAttribute('data-qa-index'));
          if (Number.isNaN(idx)) continue;

          if (entry.intersectionRatio > bestRatio) {
            bestRatio = entry.intersectionRatio;
            bestIdx = idx;
          }
        }

        if (bestIdx !== -1) {
          setActivePairIndex(bestIdx);
        }
      },
      { threshold: [0, 0.3, 0.5, 0.7, 1.0] },
    );

    // 현재 등록된 모든 QA ref 관찰
    const currentRefs = qaRefs.current;
    for (const [, el] of currentRefs) {
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, [qaPairs.length]);

  // 새 메시지 추가 시 자동 스크롤
  useEffect(() => {
    if (!pendingScrollRef.current) return;
    pendingScrollRef.current = false;

    requestAnimationFrame(() => {
      const lastIdx = qaPairs.length - 1;
      const element = qaRefs.current.get(lastIdx);
      element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }, [qaPairs.length]);

  const scrollToLatest = useCallback(() => {
    pendingScrollRef.current = true;
  }, []);

  return {
    qaPairs,
    qaRefs,
    scrollToLatest,
    activePairIndex,
  };
};

export default useRagScroll;
