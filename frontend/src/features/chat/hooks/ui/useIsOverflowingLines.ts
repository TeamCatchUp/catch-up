/**
 * 요소가 지정된 줄 수를 넘어 오버플로우되는지 감지하는 훅
 *
 * - ResizeObserver로 요소 크기 변경 감지
 * - requestAnimationFrame으로 성능 최적화
 * - watch 의존성으로 외부 상태 변경 감지
 */

import { type RefObject, useEffect, useState } from 'react';

/** line-height 파싱 실패 시 사용할 기본값 (px) */
const FALLBACK_LINE_HEIGHT_PX = 36;

/** 부동소수점 오차를 고려한 오버플로우 판단 임계값 (px) */
const HEIGHT_EPSILON_PX = 1;

interface UseIsOverflowingLinesParams {
  /** 측정 대상 요소의 ref */
  elementRef: RefObject<HTMLElement | null>;
  /** 허용할 최대 줄 수 */
  lineCount: number;
  /** 외부 상태 변경을 감지할 의존성 (예: content 문자열) */
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

    /** 요소의 실제 높이가 허용된 줄 수를 초과하는지 측정 */
    const measureOverflow = () => {
      const element = elementRef.current;
      if (!element) {
        setIsOverflowing(false);
        return;
      }

      // line-height 계산 (CSS에서 파싱 실패 시 fallback 사용)
      const computedStyle = window.getComputedStyle(element);
      const parsedLineHeight = Number.parseFloat(computedStyle.lineHeight);
      const lineHeight = Number.isNaN(parsedLineHeight)
        ? FALLBACK_LINE_HEIGHT_PX
        : parsedLineHeight;

      // 허용된 최대 높이를 초과하는지 확인 (epsilon 고려)
      const maxHeight = lineHeight * lineCount;
      const nextOverflowing = element.scrollHeight > maxHeight + HEIGHT_EPSILON_PX;
      setIsOverflowing((prev) => (prev === nextOverflowing ? prev : nextOverflowing));
    };

    /** RAF를 사용해 측정 스케줄링 (이전 요청 취소 후 새 요청) */
    const scheduleMeasure = () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
      frameId = window.requestAnimationFrame(measureOverflow);
    };

    // 초기 측정
    scheduleMeasure();

    // ResizeObserver로 요소 크기 변경 감지
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
