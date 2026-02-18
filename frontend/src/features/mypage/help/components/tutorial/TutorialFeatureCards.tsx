'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Image from 'next/image';

import { TUTORIAL_1_FEATURE_CARDS } from '@/features/mypage/help/constants/tutorialData';
import ArrowForward from '@/public/icons/icon/arrow_forward.svg';

const CARD_SCROLL_AMOUNT = 340; // card width (320) + gap (20)

const TutorialFeatureCards = () => {
  const scrollRef = useRef<HTMLUListElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const dragState = useRef({ startX: 0, scrollLeft: 0, moved: false });

  const checkScrollRight = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    checkScrollRight();
    el.addEventListener('scroll', checkScrollRight, { passive: true });
    return () => el.removeEventListener('scroll', checkScrollRight);
  }, [checkScrollRight]);

  const handleScrollRight = () => {
    scrollRef.current?.scrollBy({ left: CARD_SCROLL_AMOUNT, behavior: 'smooth' });
  };

  const handlePointerDown = (e: React.PointerEvent) => {
    const el = scrollRef.current;
    if (!el) return;
    setIsDragging(true);
    dragState.current = { startX: e.clientX, scrollLeft: el.scrollLeft, moved: false };
    el.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging) return;
    const el = scrollRef.current;
    if (!el) return;
    const dx = e.clientX - dragState.current.startX;
    if (Math.abs(dx) > 3) dragState.current.moved = true;
    el.scrollLeft = dragState.current.scrollLeft - dx;
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (!isDragging) return;
    setIsDragging(false);
    scrollRef.current?.releasePointerCapture(e.pointerId);
  };

  return (
    <div className="relative w-full" onMouseEnter={() => setIsHovered(true)} onMouseLeave={() => setIsHovered(false)}>
      <ul
        ref={scrollRef}
        className={`no-scrollbar flex gap-5 overflow-x-auto select-none ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        {TUTORIAL_1_FEATURE_CARDS.map((card) => (
          <li
            key={card.title}
            className="border-neutral-3 shadow-card flex w-80 shrink-0 flex-col gap-4 rounded-2xl border bg-white p-4"
          >
            <div className="border-neutral-3 relative aspect-1416/600 w-full overflow-hidden rounded-xl border-b">
              <Image src={card.image} alt={card.title} fill className="object-cover" />
            </div>
            <h3 className="text-heading-medium text-gray-80">{card.title}</h3>
            <p className="text-label-small text-gray-60 whitespace-pre-line">{card.description}</p>
          </li>
        ))}
      </ul>

      {/* 우측 그라데이션 페이드 */}
      <div className="pointer-events-none absolute top-0 right-0 h-full w-15.5 bg-linear-to-r from-transparent to-white" />

      {/* FAB: 오른쪽 스크롤 버튼 */}
      <button
        onClick={handleScrollRight}
        className={`border-neutral-3 absolute top-1/2 right-0 flex size-10 translate-x-1/2 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full border bg-white shadow-md transition-opacity ${
          isHovered && canScrollRight ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
      >
        <ArrowForward className="text-gray-70 h-5 w-5" />
      </button>
    </div>
  );
};

export default TutorialFeatureCards;
