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
        <div className="h-px flex-1 bg-edge-neutral" />
        <div className="flex items-center gap-2">
          <span className="text-body-small text-content-neutral">빠르게 시작하기</span>
          <IconArrowOutward className="h-5 w-5 text-icon-neutral" />
        </div>
        <div className="h-px flex-1 bg-edge-neutral" />
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
                'h-9 shrink-0 cursor-pointer rounded-rounded px-3 py-1.5 text-body-small whitespace-nowrap transition-colors',
                selectedIndex === idx
                  ? 'bg-accent-black-lighten text-content-inverse'
                  : 'border border-edge-neutral bg-fill-normal text-content-neutral',
              )}
            >
              {tip.chipLabel}
            </button>
          ))}
        </div>

        {canScrollLeft && (
          <>
            <div className="pointer-events-none absolute top-0 left-0 h-9 w-21 bg-linear-to-r from-fill-normal to-transparent" />
            <button
              type="button"
              onClick={scrollLeftBy}
              className="absolute top-1/2 left-0 flex -translate-y-1/2 cursor-pointer items-center justify-center rounded-rounded border border-edge-normal bg-fill-normal p-1.5 shadow-button"
            >
              <IconArrowLeft className="h-6 w-6 text-icon-neutral" />
            </button>
          </>
        )}

        {canScrollRight && (
          <>
            <div className="pointer-events-none absolute top-0 right-0 h-9 w-21 bg-linear-to-l from-fill-normal to-transparent" />
            <button
              type="button"
              onClick={scrollRightBy}
              className="absolute top-1/2 right-0 flex -translate-y-1/2 cursor-pointer items-center justify-center rounded-rounded border border-edge-normal bg-fill-normal p-1.5 shadow-button"
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
