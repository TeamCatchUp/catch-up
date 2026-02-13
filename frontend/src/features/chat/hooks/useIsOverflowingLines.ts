import { type RefObject, useEffect, useState } from 'react';

const FALLBACK_LINE_HEIGHT_PX = 36;
const HEIGHT_EPSILON_PX = 1;

interface UseIsOverflowingLinesParams {
  elementRef: RefObject<HTMLElement | null>;
  lineCount: number;
  watch?: string;
}

export const useIsOverflowingLines = ({
  elementRef,
  lineCount,
  watch,
}: UseIsOverflowingLinesParams) => {
  const [isOverflowing, setIsOverflowing] = useState(false);

  useEffect(() => {
    let frameId: number | null = null;
    let observer: ResizeObserver | null = null;

    const measureOverflow = () => {
      const element = elementRef.current;
      if (!element) {
        setIsOverflowing(false);
        return;
      }

      const computedStyle = window.getComputedStyle(element);
      const parsedLineHeight = Number.parseFloat(computedStyle.lineHeight);
      const lineHeight = Number.isNaN(parsedLineHeight)
        ? FALLBACK_LINE_HEIGHT_PX
        : parsedLineHeight;

      const maxHeight = lineHeight * lineCount;
      const nextOverflowing = element.scrollHeight > maxHeight + HEIGHT_EPSILON_PX;
      setIsOverflowing((prev) => (prev === nextOverflowing ? prev : nextOverflowing));
    };

    const scheduleMeasure = () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
      frameId = window.requestAnimationFrame(measureOverflow);
    };

    scheduleMeasure();

    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(scheduleMeasure);
      const element = elementRef.current;
      if (element) {
        observer.observe(element);
      }
    }

    return () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
      observer?.disconnect();
    };
  }, [elementRef, lineCount, watch]);

  return isOverflowing;
};
