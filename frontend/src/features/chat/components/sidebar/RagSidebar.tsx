'use client';

import { useEffect, useRef, useState } from 'react';

import StepHistoryScroller from '@/features/chat/components/skeleton/StepHistoryScroller';
import type { PipelineQueryType, StepRow } from '@/features/chat/types';
import type { QAPair } from '@/features/chat/utils/render/chat';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { cn } from '@/shared/utils/cn';

import SourceList from './source/SourceList';

const SIDEBAR_FADE_MS = 160;
const SIDEBAR_SHIFT_PX = 8;

const SHOWING_PIPELINE_TYPES: ReadonlySet<PipelineQueryType> = new Set([
  'simple',
  'standard',
  'complex',
]);

interface RagSidebarProps {
  currentQA: QAPair | undefined;
  isLoading: boolean;
  isError: boolean;
  stepRows: StepRow[];
  topic: string | null;
  pipelineQueryType: PipelineQueryType | null;
  pipelineReasoning: string | null;
}

export default function RagSidebar({
  currentQA,
  isLoading,
  isError,
  stepRows,
  topic,
  pipelineQueryType,
  pipelineReasoning,
}: RagSidebarProps) {
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
  const answerContent = effectiveQA?.answer?.content ?? '';

  const transitionClass = prefersReducedMotion
    ? ''
    : cn('transition-[opacity,transform] duration-160 ease-out', isVisible ? 'translate-y-0 opacity-100' : 'opacity-0');

  const transitionStyle = prefersReducedMotion
    ? undefined
    : { transform: `translateY(${isVisible ? 0 : SIDEBAR_SHIFT_PX}px)` };

  // 답변 생성 중엔 step history, 종료 시점부터 SourceList. 검색 파이프라인 분류일 때만 step 노출.
  const showStepSkeleton =
    isLoading && pipelineQueryType !== null && SHOWING_PIPELINE_TYPES.has(pipelineQueryType);

  return (
    <div className="border-edge-neutral bg-fill-normal hidden w-108.75 flex-none flex-col border-l lg:flex">
      <div
        className={cn('flex min-h-0 flex-1 flex-col overflow-hidden', transitionClass)}
        style={transitionStyle}
      >
        {showStepSkeleton ? (
          <StepHistoryScroller stepRows={stepRows} topic={topic} />
        ) : (
          <SourceList
            sources={sources}
            answerContent={answerContent}
            isLoading={isLoading}
            isError={isError}
            transitionKey={transitionKey}
            prefersReducedMotion={prefersReducedMotion}
          />
        )}
      </div>
    </div>
  );
}
