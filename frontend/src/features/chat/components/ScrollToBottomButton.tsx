'use client';

import { type RefObject,useEffect, useState } from 'react';

import ArrowDown from '@/public/icons/icon/arrow_down.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

interface ScrollToBottomButtonProps {
  scrollContainerRef: RefObject<HTMLDivElement | null>;
}

const SCROLL_THRESHOLD_PX = 100;

export default function ScrollToBottomButton({ scrollContainerRef }: ScrollToBottomButtonProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const check = () => {
      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      setVisible(distanceFromBottom > SCROLL_THRESHOLD_PX);
    };

    check();
    container.addEventListener('scroll', check, { passive: true });
    return () => container.removeEventListener('scroll', check);
  }, [scrollContainerRef]);

  const handleClick = () => {
    const container = scrollContainerRef.current;
    container?.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
  };

  return (
    <Button
      variant="fab-secondary"
      size="md"
      type="button"
      onClick={handleClick}
      aria-label="맨 아래로 이동"
      className={cn(
        'z-fab absolute bottom-6 left-1/2 -translate-x-1/2 transition-opacity duration-150',
        visible ? 'opacity-100' : 'pointer-events-none opacity-0',
      )}
    >
      <ArrowDown className="h-6 w-6" />
    </Button>
  );
}
