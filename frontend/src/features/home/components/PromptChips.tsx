'use client';

import IconArrowLeft from '@/public/icons/icon/arrow_left2.svg';
import IconArrowOutward from '@/public/icons/icon/arrow_outward.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

import { tipData } from '../constants/questionTips';
import { useCarouselScroll } from '../hooks/useCarouselScroll';

interface PromptChipsProps {
  onChipClick: (index: number) => void;
  selectedIndex: number | null;
}

const PromptChips = ({ onChipClick, selectedIndex }: PromptChipsProps) => {
  const {
    scrollRef,
    canScrollLeft,
    canScrollRight,
    scrollLeftBy,
    scrollRightBy,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleItemClick,
  } = useCarouselScroll({ scrollAmount: 200 });

  const onChipClickSafe = handleItemClick(onChipClick);

  return (
    <section className="flex w-190 flex-col gap-4">
      {/* 빠르게 시작하기 디바이더 */}
      <div className="flex items-center gap-8">
        <div className="bg-edge-neutral h-px flex-1" />
        <div className="flex items-center gap-2">
          <span className="text-body-small text-content-neutral">빠르게 시작하기</span>
          <IconArrowOutward className="text-icon-neutral h-5 w-5" />
        </div>
        <div className="bg-edge-neutral h-px flex-1" />
      </div>

      {/* 칩 스크롤 컨테이너 */}
      <div className="relative">
        <div
          ref={scrollRef}
          className="no-scrollbar flex cursor-grab gap-3 overflow-x-auto select-none"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {tipData.map((tip, idx) => (
            <button
              key={tip.title}
              type="button"
              onClick={() => onChipClickSafe(idx)}
              className={cn(
                'rounded-rounded text-body-small h-9 shrink-0 cursor-pointer px-3 py-1.5 whitespace-nowrap transition-colors',
                selectedIndex === idx
                  ? 'bg-accent-black-lighten text-content-inverse'
                  : 'border-edge-neutral bg-fill-normal text-content-neutral border',
              )}
            >
              {tip.chipLabel}
            </button>
          ))}
        </div>

        {canScrollLeft && (
          <>
            <div className="from-fill-normal pointer-events-none absolute top-0 left-0 h-9 w-21 bg-linear-to-r to-transparent" />
            <button
              type="button"
              onClick={scrollLeftBy}
              className="rounded-rounded border-edge-normal bg-fill-normal shadow-button absolute top-1/2 left-0 flex -translate-y-1/2 cursor-pointer items-center justify-center border p-1.5"
            >
              <IconArrowLeft className="text-icon-neutral h-6 w-6" />
            </button>
          </>
        )}

        {canScrollRight && (
          <>
            <div className="from-fill-normal pointer-events-none absolute top-0 right-0 h-9 w-21 bg-linear-to-l to-transparent" />
            <button
              type="button"
              onClick={scrollRightBy}
              className="rounded-rounded border-edge-normal bg-fill-normal shadow-button absolute top-1/2 right-0 flex -translate-y-1/2 cursor-pointer items-center justify-center border p-1.5"
            >
              <IconArrowRight className="text-icon-neutral h-6 w-6" />
            </button>
          </>
        )}
      </div>
    </section>
  );
};

export default PromptChips;
