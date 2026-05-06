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
 * 사이드바 답변 생성 과정 wrapper. 사용자가 bottom 근처(100px 이내)에 있을 때만
 * 새 row 도착 시 부드럽게 자동 스크롤. 위로 직접 스크롤하면 멈춘다.
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
    const raf = requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: reduceMotion ? 'auto' : 'smooth' });
    });
    return () => cancelAnimationFrame(raf);
  }, [stepRows, reduceMotion]);

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto"
    >
      <TopicHeader topic={topic} />
      <div className="px-6 pt-2 pb-4">
        <StepHistory rows={stepRows} />
      </div>
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
