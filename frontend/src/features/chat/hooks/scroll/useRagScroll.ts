/**
 * useRagScroll
 * 연속 스크롤 기반 Q&A 렌더링 + Intersection Observer 사이드바 연동
 * useRagPagination 대체
 */

'use client';

import type { RefObject } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { Message } from '@/features/chat/types';
import { extractQAPairs, type QAPair } from '@/features/chat/utils/render/chat';

import { pickBestActiveIndex } from './pickBestActiveIndex';

interface UseRagScrollOptions {
  messages: Message[];
  /** 특정 메시지로 스크롤하기 위한 메시지 ID (RecentQueryResponse.id) */
  scrollToMessageId?: string | null;
  /** 스크롤 완료 후 호출되는 콜백 (URL 파라미터 정리 등) */
  onScrollToComplete?: () => void;
}

interface UseRagScrollReturn {
  qaPairs: QAPair[];
  qaRefs: RefObject<Map<number, HTMLDivElement | null>>;
  scrollContainerCallbackRef: (node: HTMLDivElement | null) => void;
  scrollContainerHeight: number;
  scrollToLatest: () => void;
  activePairIndex: number;
  /**
   * 무한 스크롤 prepend 후 activePairIndex가 같은 인덱스로 다른 페어를 가리키지 않도록
   * 외부에서 prepend된 페어 수만큼 보정한다.
   */
  shiftActivePairIndex: (by: number) => void;
}

const OBSERVER_THRESHOLDS = [0, 0.15, 0.3, 0.5, 0.7, 1.0];
const HYSTERESIS_PX = 48;

export const useRagScroll = ({
  messages,
  scrollToMessageId,
  onScrollToComplete,
}: UseRagScrollOptions): UseRagScrollReturn => {
  const qaPairs = useMemo(() => extractQAPairs(messages), [messages]);
  const qaRefs = useRef<Map<number, HTMLDivElement | null>>(new Map());
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const intersectingEntriesRef = useRef<Map<number, IntersectionObserverEntry>>(new Map());
  const activePairIndexRef = useRef(0);

  const [scrollContainerHeight, setScrollContainerHeight] = useState(0);
  const [activePairIndex, setActivePairIndex] = useState(0);
  const [observerSeed, setObserverSeed] = useState(0);

  const pendingScrollRef = useRef(false);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const clampedActivePairIndex = qaPairs.length === 0 ? 0 : Math.min(activePairIndex, qaPairs.length - 1);

  // sync merge 후 message ID가 변경되면 DOM 요소가 교체되므로
  // IntersectionObserver가 새 요소를 다시 observe
  const qaPairKey = useMemo(() => qaPairs.map((p) => p.question.id).join(','), [qaPairs]);

  useEffect(() => {
    activePairIndexRef.current = clampedActivePairIndex;
  }, [clampedActivePairIndex]);

  const scrollContainerCallbackRef = useCallback((node: HTMLDivElement | null) => {
    scrollContainerRef.current = node;
    setObserverSeed((prev) => prev + 1);

    if (resizeObserverRef.current) {
      resizeObserverRef.current.disconnect();
      resizeObserverRef.current = null;
    }

    if (!node) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setScrollContainerHeight(entry.contentRect.height);
      }
    });

    observer.observe(node);
    resizeObserverRef.current = observer;
  }, []);

  useEffect(() => {
    const root = scrollContainerRef.current;
    if (!root) return;

    const observedEntries = intersectingEntriesRef.current;
    observedEntries.clear();

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const idx = Number(entry.target.getAttribute('data-qa-index'));
          if (Number.isNaN(idx)) continue;

          if (!entry.isIntersecting) {
            observedEntries.delete(idx);
            continue;
          }

          observedEntries.set(idx, entry);
        }

        const next = pickBestActiveIndex({
          observedEntries,
          rootRect: root.getBoundingClientRect(),
          currentIdx: activePairIndexRef.current,
          hysteresisPx: HYSTERESIS_PX,
        });

        if (next !== null) {
          setActivePairIndex(next);
        }
      },
      {
        root,
        threshold: OBSERVER_THRESHOLDS,
      },
    );

    const currentRefs = qaRefs.current;
    for (const [, el] of currentRefs) {
      if (el) observer.observe(el);
    }

    return () => {
      observer.disconnect();
      observedEntries.clear();
    };
  }, [observerSeed, qaPairKey]);

  // scrollToMessageId가 지정된 경우 해당 Q&A pair로 스크롤
  const scrollToHandledRef = useRef(false);

  // scrollToMessageId 변경 시 handled 플래그 초기화 (같은 세션 내 재스크롤 지원)
  useEffect(() => {
    scrollToHandledRef.current = false;
  }, [scrollToMessageId]);

  useEffect(() => {
    if (!scrollToMessageId || scrollToHandledRef.current || qaPairs.length === 0) return;

    const targetId = String(scrollToMessageId);
    const targetIndex = qaPairs.findIndex((p) => p.question.id === targetId);
    if (targetIndex < 0) return;

    scrollToHandledRef.current = true;

    requestAnimationFrame(() => {
      const element = qaRefs.current.get(targetIndex);
      element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      onScrollToComplete?.();
    });
  }, [scrollToMessageId, qaPairs, onScrollToComplete]);

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

  const shiftActivePairIndex = useCallback((by: number) => {
    if (!by) return;
    setActivePairIndex((prev) => Math.max(0, prev + by));
  }, []);

  return {
    qaPairs,
    qaRefs,
    scrollContainerCallbackRef,
    scrollContainerHeight,
    scrollToLatest,
    activePairIndex: clampedActivePairIndex,
    shiftActivePairIndex,
  };
};

export default useRagScroll;
