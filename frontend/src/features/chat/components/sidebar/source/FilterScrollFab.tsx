'use client';

import { useEffect, useState } from 'react';

import ArrowLeft from '@/public/icons/icon/arrow_left2.svg';
import ArrowRight from '@/public/icons/icon/arrow_right2.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

interface Props {
  container: HTMLDivElement | null;
}

const EDGE_THRESHOLD_PX = 4;
const SCROLL_RATIO = 0.7;

export default function FilterScrollFab({ container }: Props) {
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  useEffect(() => {
    if (!container) return;

    const check = () => {
      const { scrollLeft, scrollWidth, clientWidth } = container;
      setCanScrollLeft(scrollLeft > EDGE_THRESHOLD_PX);
      setCanScrollRight(scrollLeft + clientWidth < scrollWidth - EDGE_THRESHOLD_PX);
    };

    check();
    container.addEventListener('scroll', check, { passive: true });
    const observer = new ResizeObserver(check);
    observer.observe(container);

    return () => {
      container.removeEventListener('scroll', check);
      observer.disconnect();
    };
  }, [container]);

  const scrollBy = (delta: number) => {
    container?.scrollBy({ left: delta, behavior: 'smooth' });
  };

  return (
    <>
      <Button
        variant="fab-secondary"
        size="sm"
        type="button"
        onClick={() => scrollBy(-(container?.clientWidth ?? 0) * SCROLL_RATIO)}
        aria-label="필터 좌측으로 이동"
        className={cn(
          'z-fab absolute top-1/2 left-2 -translate-y-1/2 transition-opacity duration-150',
          canScrollLeft ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      >
        <ArrowLeft className="h-5 w-5" />
      </Button>
      <Button
        variant="fab-secondary"
        size="sm"
        type="button"
        onClick={() => scrollBy((container?.clientWidth ?? 0) * SCROLL_RATIO)}
        aria-label="필터 우측으로 이동"
        className={cn(
          'z-fab absolute top-1/2 right-2 -translate-y-1/2 transition-opacity duration-150',
          canScrollRight ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      >
        <ArrowRight className="h-5 w-5" />
      </Button>
    </>
  );
}
