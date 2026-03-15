'use client';

import { useEffect, useRef, useState } from 'react';

import type { QAPair } from '@/features/chat/utils/render/chat';
import { cn } from '@/shared/utils/cn';

import SidebarHeader from './SidebarHeader';
import SourceList from './source/SourceList';

const SIDEBAR_FADE_MS = 160;
const SIDEBAR_SHIFT_PX = 8;

interface RagSidebarProps {
  currentQA: QAPair | undefined;
  isLoading: boolean;
  isError: boolean;
}

const usePrefersReducedMotion = () => {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = () => setPrefersReducedMotion(mediaQuery.matches);

    onChange();
    mediaQuery.addEventListener('change', onChange);

    return () => {
      mediaQuery.removeEventListener('change', onChange);
    };
  }, []);

  return prefersReducedMotion;
};

const RagSidebar = ({ currentQA, isLoading, isError }: RagSidebarProps) => {
  const [displayQA, setDisplayQA] = useState<QAPair | undefined>(currentQA);
  const [isVisible, setIsVisible] = useState(true);
  const transitionTimerRef = useRef<number | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (prefersReducedMotion) {
      if (transitionTimerRef.current) {
        window.clearTimeout(transitionTimerRef.current);
        transitionTimerRef.current = null;
      }
      return;
    }

    if (displayQA?.question.id === currentQA?.question.id) return;

    if (transitionTimerRef.current) {
      window.clearTimeout(transitionTimerRef.current);
      transitionTimerRef.current = null;
    }

    const rafId = window.requestAnimationFrame(() => {
      setIsVisible(false);

      transitionTimerRef.current = window.setTimeout(() => {
        setDisplayQA(currentQA);
        setIsVisible(true);
        transitionTimerRef.current = null;
      }, SIDEBAR_FADE_MS);
    });

    return () => {
      window.cancelAnimationFrame(rafId);
      if (!transitionTimerRef.current) return;
      window.clearTimeout(transitionTimerRef.current);
      transitionTimerRef.current = null;
    };
  }, [currentQA, displayQA?.question.id, prefersReducedMotion]);

  useEffect(() => {
    return () => {
      if (!transitionTimerRef.current) return;
      window.clearTimeout(transitionTimerRef.current);
    };
  }, []);

  const transitionKey = displayQA?.question.id ?? 'empty';
  // 같은 QA pair → currentQA(최신 데이터), 전환 중 → displayQA(이전 pair 유지)
  const effectiveQA = displayQA?.question.id === currentQA?.question.id ? currentQA : displayQA;
  const sources = effectiveQA?.answer?.sources ?? [];
  const sourceCount = sources.filter((source) => source.is_cited).length;
  const answerContent = effectiveQA?.answer?.content ?? '';

  const transitionClass = prefersReducedMotion
    ? ''
    : cn('transition-[opacity,transform] duration-160 ease-out', isVisible ? 'translate-y-0 opacity-100' : 'opacity-0');

  const transitionStyle = prefersReducedMotion
    ? undefined
    : { transform: `translateY(${isVisible ? 0 : SIDEBAR_SHIFT_PX}px)` };

  return (
    <div className="border-edge-neutral bg-fill-normal hidden w-100 flex-none flex-col border-l lg:flex">
      <SidebarHeader sourceCount={sourceCount} className={transitionClass} />
      <div className={cn('min-h-0 flex-1 overflow-y-auto', transitionClass)} style={transitionStyle}>
        <SourceList
          sources={sources}
          answerContent={answerContent}
          isLoading={isLoading}
          isError={isError}
          transitionKey={transitionKey}
          prefersReducedMotion={prefersReducedMotion}
        />
      </div>
    </div>
  );
};

export default RagSidebar;
