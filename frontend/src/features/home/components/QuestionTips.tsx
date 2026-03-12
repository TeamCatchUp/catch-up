'use client';

import Image from 'next/image';

import IconArrowLeft from '@/public/icons/icon/arrow_left2.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import Book from '@/public/icons/icon/book.svg';

import { tipData } from '../constants/questionTips';
import { useCarouselScroll } from '../hooks/useCarouselScroll';

interface QuestionTipsProps {
  onTipClick: (index: number) => void;
}

const QuestionTips = ({ onTipClick }: QuestionTipsProps) => {
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
  } = useCarouselScroll({ scrollAmount: 260 });

  const onCardClick = handleItemClick(onTipClick);

  return (
    <section className="flex w-268 flex-col gap-4">
      <header className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg border-[0.5px] border-edge-neutral bg-fill-primary-assistive">
          <Book className="h-6 w-6 text-icon-primary" />
        </div>
        <h2 className="text-heading-large text-content-normal">질문 작성을 도와드릴게요!</h2>
      </header>

      <div className="relative">
        <div
          ref={scrollRef}
          className="no-scrollbar flex cursor-grab gap-5 overflow-x-auto select-none"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {tipData.map((tip, idx) => (
            <button
              key={tip.title}
              type="button"
              onClick={() => onCardClick(idx)}
              className="flex h-[226px] w-60 shrink-0 cursor-pointer flex-col overflow-hidden rounded-2xl border border-edge-neutral bg-fill-normal text-left"
            >
              <div className="relative h-[119px] w-full overflow-hidden">
                <Image src={tip.image} alt={tip.title} fill draggable={false} className="object-cover dark:hidden" />
                <Image
                  src={tip.image.replace('/light/', '/dark/')}
                  alt={tip.title}
                  fill
                  draggable={false}
                  className="hidden object-cover dark:block"
                />
              </div>
              <div className="flex flex-col gap-1.5 px-5 py-4">
                <p className="text-heading-small text-content-normal">{tip.title}</p>
                <p className="text-label-small whitespace-pre-line text-content-alternative">{tip.description}</p>
              </div>
            </button>
          ))}
        </div>

        {canScrollLeft && (
          <>
            <div className="pointer-events-none absolute top-0 left-0 h-full w-20 bg-linear-to-r from-fill-normal to-transparent" />
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
            <div className="pointer-events-none absolute top-0 right-0 h-full w-20 bg-linear-to-l from-fill-normal to-transparent" />
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

export default QuestionTips;
