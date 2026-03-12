'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import IconArrowOutward from '@/public/icons/icon/arrow_outward.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

import { tipData } from '../constants/questionTips';

interface PromptChipsProps {
  onChipClick: (index: number) => void;
  selectedIndex: number | null;
}

const PromptChips = ({ onChipClick, selectedIndex }: PromptChipsProps) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const checkScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    checkScroll();
    el.addEventListener('scroll', checkScroll, { passive: true });
    return () => el.removeEventListener('scroll', checkScroll);
  }, [checkScroll]);

  const scrollRight = () => {
    scrollRef.current?.scrollBy({ left: 200, behavior: 'smooth' });
  };

  return (
    <section className="flex w-190 flex-col gap-4">
      {/* 빠르게 시작하기 디바이더 */}
      <div className="flex items-center gap-8">
        <div className="h-px flex-1 bg-edge-neutral" />
        <div className="flex items-center gap-2">
          <span className="text-body-small text-content-neutral">빠르게 시작하기</span>
          <IconArrowOutward className="h-5 w-5 text-icon-neutral" />
        </div>
        <div className="h-px flex-1 bg-edge-neutral" />
      </div>

      {/* 칩 스크롤 컨테이너 */}
      <div className="relative">
        <div ref={scrollRef} className="no-scrollbar flex gap-3 overflow-x-auto">
          {tipData.map((tip, idx) => (
            <button
              key={tip.title}
              type="button"
              onClick={() => onChipClick(idx)}
              className={cn(
                'h-9 shrink-0 cursor-pointer rounded-rounded px-3 py-1.5 text-body-small whitespace-nowrap transition-colors',
                selectedIndex === idx
                  ? 'bg-accent-black-lighten text-content-inverse'
                  : 'border border-edge-neutral bg-fill-normal text-content-neutral',
              )}
            >
              {tip.title}
            </button>
          ))}
        </div>

        {/* 우측 페이드 + 스크롤 화살표 */}
        {canScrollRight && (
          <>
            <div className="pointer-events-none absolute top-0 right-0 h-9 w-21 bg-gradient-to-l from-fill-normal to-transparent" />
            <button
              type="button"
              onClick={scrollRight}
              className="shadow-button border-edge-normal bg-fill-normal absolute top-1/2 right-0 flex -translate-y-1/2 cursor-pointer items-center justify-center rounded-rounded border p-1.5"
            >
              <IconArrowRight className="h-6 w-6 text-icon-neutral" />
            </button>
          </>
        )}
      </div>
    </section>
  );
};

export default PromptChips;
