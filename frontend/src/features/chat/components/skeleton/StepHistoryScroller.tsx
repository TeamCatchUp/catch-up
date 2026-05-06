'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import StepHistory from '@/features/chat/components/skeleton/StepHistory';
import TopicHeader from '@/features/chat/components/skeleton/TopicHeader';
import type { StepRow } from '@/features/chat/types';

const STICK_THRESHOLD_PX = 100;

interface StepHistoryScrollerProps {
  stepRows: StepRow[];
  topic: string | null;
}

/**
 * 사이드바 내부 답변 생성 과정 wrapper.
 *
 * Auto-scroll 정책 (b):
 *  - 사용자가 bottom 근처(100px 이내)에 있을 때만 새 row 추가 시 자동 bottom 스크롤
 *  - 사용자가 위로 직접 스크롤하면 자동 스크롤 멈춤 → bottom 근처로 다시 내려오면 재개
 *  - `behavior: 'smooth'`로 부드럽게 이동. `prefers-reduced-motion: reduce`면 즉시 이동
 *
 * stepRows reference 변경(새 row push, completedItems 누적)을 effect dependency로 추적.
 */
export default function StepHistoryScroller({ stepRows, topic }: StepHistoryScrollerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const isStickToBottomRef = useRef(true);
  const reduceMotion = usePrefersReducedMotion();

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    isStickToBottomRef.current = distanceFromBottom <= STICK_THRESHOLD_PX;
  }, []);

  useEffect(() => {
    if (!isStickToBottomRef.current) return;
    const el = scrollRef.current;
    if (!el) return;
    // Layout 적용 후 scrollHeight를 읽어 정확한 bottom으로 이동
    const raf = requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: reduceMotion ? 'auto' : 'smooth' });
    });
    return () => cancelAnimationFrame(raf);
  }, [stepRows, reduceMotion]);

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-4"
    >
      <TopicHeader topic={topic} />
      <StepHistory rows={stepRows} />
    </div>
  );
}

const usePrefersReducedMotion = () => {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = () => setReduce(mq.matches);
    onChange();
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return reduce;
};
