'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Image from 'next/image';

import IconArrowLeft from '@/public/icons/icon/arrow_left2.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import Book from '@/public/icons/icon/book.svg';

import { tipData } from '../constants/questionTips';

interface QuestionTipsProps {
  onTipClick: (index: number) => void;
}

const QuestionTips = ({ onTipClick }: QuestionTipsProps) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const dragStartX = useRef(0);
  const dragScrollLeft = useRef(0);
  const hasDragged = useRef(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const checkScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 1);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    checkScroll();
    el.addEventListener('scroll', checkScroll, { passive: true });
    return () => el.removeEventListener('scroll', checkScroll);
  }, [checkScroll]);

  const scrollLeft = () => {
    scrollRef.current?.scrollBy({ left: -260, behavior: 'smooth' });
  };

  const scrollRight = () => {
    scrollRef.current?.scrollBy({ left: 260, behavior: 'smooth' });
  };

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const el = scrollRef.current;
    if (!el) return;
    isDragging.current = true;
    hasDragged.current = false;
    dragStartX.current = e.pageX;
    dragScrollLeft.current = el.scrollLeft;
    el.style.cursor = 'grabbing';
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current || !scrollRef.current) return;
    const dx = e.pageX - dragStartX.current;
    if (Math.abs(dx) > 3) hasDragged.current = true;
    scrollRef.current.scrollLeft = dragScrollLeft.current - dx;
  }, []);

  const handleMouseUp = useCallback(() => {
    isDragging.current = false;
    if (scrollRef.current) scrollRef.current.style.cursor = '';
  }, []);

  const handleCardClick = useCallback(
    (idx: number) => {
      if (hasDragged.current) return;
      onTipClick(idx);
    },
    [onTipClick],
  );

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
              onClick={() => handleCardClick(idx)}
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
              onClick={scrollLeft}
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
              onClick={scrollRight}
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
