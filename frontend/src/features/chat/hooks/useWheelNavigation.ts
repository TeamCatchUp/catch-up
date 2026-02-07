/**
 * 휠 기반 페이지 네비게이션 훅
 * 트랙패드/마우스 휠로 페이지 전환을 처리
 * 휠 이벤트 감지만 담당, 실제 페이지 전환은 pagination 훅에서 처리
 */

'use client';

import { useCallback, useEffect, useRef } from 'react';
import { WHEEL_CONFIG, ANIMATION_CONFIG } from '@/features/chat/constants/config';

interface UseWheelNavigationOptions {
  /** 휠 이벤트를 감지할 컨테이너 ref */
  containerRef: React.RefObject<HTMLDivElement | null>;
  /** 휠 이벤트를 무시할 영역들의 ref (스크롤 가능한 내부 영역) */
  excludeRefs?: React.RefObject<HTMLElement | null>[];
  /** 전체 페이지 수 */
  totalPages: number;
  /** 현재 페이지 인덱스 */
  currentPage: number;
  /** 비활성화 여부 (로딩 중 등) */
  disabled?: boolean;
  /** 페이지 변경 콜백 */
  onPageChange: (page: number) => void;
  /** 슬라이드 방향 변경 콜백 (애니메이션용) */
  onSlideDirectionChange?: (direction: 'up' | 'down' | null) => void;
}

/** 휠 네비게이션 훅 */
export const useWheelNavigation = ({
  containerRef,
  excludeRefs = [],
  totalPages,
  currentPage,
  disabled = false,
  onPageChange,
  onSlideDirectionChange,
}: UseWheelNavigationOptions) => {
  // Refs for wheel handling
  const wheelAccumRef = useRef(0);
  const wheelLockRef = useRef(false);
  const wheelEndTimerRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * deltaMode에 따라 deltaY를 픽셀 단위로 정규화
   * - deltaMode 0: 픽셀 (그대로 사용)
   * - deltaMode 1: 라인 (16px로 환산)
   * - deltaMode 2: 페이지 (800px로 환산)
   */
  const normalizeDeltaY = useCallback((e: WheelEvent): number => {
    let dy = e.deltaY;

    if (e.deltaMode === 1) {
      dy *= 16; // line -> px
    } else if (e.deltaMode === 2) {
      dy *= 800; // page -> px
    }

    // 트랙패드 스파이크 완화 (너무 큰 값 제한)
    return Math.max(-100, Math.min(100, dy));
  }, []);

  /**
   * 휠 이벤트 핸들러
   */
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      // 비활성화 상태면 이벤트 차단
      if (disabled) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }

      // 제외 영역 내부에서의 이벤트는 무시 (내부 스크롤 허용)
      const isInsideExcluded = excludeRefs.some(
        (ref) => ref.current && ref.current.contains(e.target as Node),
      );
      if (isInsideExcluded) return;

      // 페이지 전환 이벤트이므로 기본 동작 차단
      e.preventDefault();
      e.stopPropagation();

      // 휠 입력 종료 타이머 갱신
      if (wheelEndTimerRef.current) {
        clearTimeout(wheelEndTimerRef.current);
      }
      wheelEndTimerRef.current = setTimeout(() => {
        wheelLockRef.current = false;
        wheelAccumRef.current = 0;
      }, WHEEL_CONFIG.END_MS);

      // 잠금 중이면 무시
      if (wheelLockRef.current) return;

      // 누적 델타 계산
      const dy = normalizeDeltaY(e);
      wheelAccumRef.current += dy;

      // 임계값 미달이면 대기
      if (Math.abs(wheelAccumRef.current) < WHEEL_CONFIG.THRESHOLD) return;

      // 이동 방향 결정 및 잠금
      const dir = wheelAccumRef.current > 0 ? 1 : -1;
      wheelLockRef.current = true;
      wheelAccumRef.current = 0;

      // 슬라이드 방향 설정
      onSlideDirectionChange?.(dir > 0 ? 'up' : 'down');

      // 페이지 변경
      const nextPage = currentPage + dir;
      if (nextPage >= 0 && nextPage < totalPages) {
        onPageChange(nextPage);
      }

      // 애니메이션 종료 후 방향 초기화
      setTimeout(() => {
        onSlideDirectionChange?.(null);
      }, ANIMATION_CONFIG.SLIDE_DURATION_MS);
    },
    [
      disabled,
      excludeRefs,
      totalPages,
      currentPage,
      normalizeDeltaY,
      onPageChange,
      onSlideDirectionChange,
    ],
  );

  // 휠 이벤트 리스너 등록
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener('wheel', handleWheel, { passive: false });

    return () => {
      container.removeEventListener('wheel', handleWheel);
      if (wheelEndTimerRef.current) {
        clearTimeout(wheelEndTimerRef.current);
      }
    };
  }, [containerRef, handleWheel]);
};

export default useWheelNavigation;
