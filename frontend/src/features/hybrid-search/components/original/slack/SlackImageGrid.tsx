'use client';

import { useEffect, useMemo, useState } from 'react';
import Image from 'next/image';

import type { SlackFileRaw } from '@/features/hybrid-search/types/slackOriginalApi';
import ArrowLeft from '@/public/icons/icon/arrow_left2.svg';
import ArrowRight from '@/public/icons/icon/arrow_right2.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface SlackImageGridProps {
  files: SlackFileRaw[];
}

const EDGE_THRESHOLD_PX = 4;
const SCROLL_RATIO = 0.7;

function getImageUrl(file: SlackFileRaw): string | null {
  const url = file.thumb_480 || file.thumb_360;
  return url && isSafeUrl(url) ? url : null;
}

export function hasSafeSlackImagePreview(file: SlackFileRaw): boolean {
  return Boolean(file.mimetype?.startsWith('image/') && getImageUrl(file));
}

export default function SlackImageGrid({ files }: SlackImageGridProps) {
  const images = useMemo(
    () =>
      files
        .map((file) => ({ file, url: getImageUrl(file) }))
        .filter((item): item is { file: SlackFileRaw; url: string } => Boolean(item.url)),
    [files],
  );
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
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

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(check);
      observer.observe(container);
    }

    return () => {
      container.removeEventListener('scroll', check);
      observer?.disconnect();
    };
  }, [container, images.length]);

  if (images.length === 0) return null;

  const scrollBy = (delta: number) => {
    container?.scrollBy({ left: delta, behavior: 'smooth' });
  };

  return (
    <div className="relative w-83.25 max-w-full overflow-hidden">
      <div
        ref={setContainer}
        data-testid="slack-image-grid-scroll"
        className="no-scrollbar flex w-full items-start gap-2.5 overflow-x-auto scroll-smooth"
      >
        {images.map(({ file, url }) => (
          <Image
            key={file.id || file.name || url}
            src={url}
            alt={file.title || file.name || ''}
            width={120}
            height={120}
            className="border-edge-neutral size-30 shrink-0 rounded-xl border object-cover"
            unoptimized
          />
        ))}
      </div>
      <Button
        variant="fab-secondary"
        size="sm"
        type="button"
        onClick={() => scrollBy(-(container?.clientWidth ?? 0) * SCROLL_RATIO)}
        aria-label="이미지 좌측으로 이동"
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
        aria-label="이미지 우측으로 이동"
        className={cn(
          'z-fab absolute top-1/2 right-2 -translate-y-1/2 transition-opacity duration-150',
          canScrollRight ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      >
        <ArrowRight className="h-5 w-5" />
      </Button>
    </div>
  );
}
