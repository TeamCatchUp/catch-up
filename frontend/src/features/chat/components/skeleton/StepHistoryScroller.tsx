'use client';

import { useCallback, useEffect, useRef } from 'react';

import StepHistory from '@/features/chat/components/skeleton/StepHistory';
import TopicHeader from '@/features/chat/components/skeleton/TopicHeader';
import type { StepRow } from '@/features/chat/types';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';

const STICK_THRESHOLD_PX = 160;

interface StepHistoryScrollerProps {
  stepRows: StepRow[];
  topic: string | null;
}

/**
 * 사이드바 답변 생성 과정 wrapper. 사용자가 bottom 근처에 있을 때만 자동 스크롤.
 * ResizeObserver로 content height 변화(새 row 추가, 박스 collapseExpand 애니메이션)를
 * 추적해 박스가 펼쳐지는 동안에도 끝까지 따라간다. 위로 직접 스크롤하면 sticky가 풀린다.
 */
export default function StepHistoryScroller({ stepRows, topic }: StepHistoryScrollerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const isStickToBottomRef = useRef(true);
  const reduceMotion = usePrefersReducedMotion();

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    isStickToBottomRef.current = distanceFromBottom <= STICK_THRESHOLD_PX;
  }, []);

  useEffect(() => {
    const scroll = scrollRef.current;
    const content = contentRef.current;
    if (!scroll || !content) return;

    let raf = 0;
    const observer = new ResizeObserver(() => {
      if (!isStickToBottomRef.current) return;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        scroll.scrollTo({ top: scroll.scrollHeight, behavior: reduceMotion ? 'auto' : 'smooth' });
      });
    });
    observer.observe(content);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [reduceMotion]);

  return (
    <div ref={scrollRef} onScroll={handleScroll} className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div ref={contentRef}>
        <TopicHeader topic={topic} />
        <div className="px-6 pt-2 pb-4">
          <StepHistory rows={stepRows} />
        </div>
      </div>
    </div>
  );
}
