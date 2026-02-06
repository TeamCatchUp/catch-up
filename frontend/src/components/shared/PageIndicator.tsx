// ============================================================
// 페이지 인디케이터 컴포넌트
// 여러 페이지/슬라이드 간 현재 위치를 표시하는 공통 컴포넌트
// ============================================================

'use client';

import clsx from 'clsx';

// ============================================================
// Types
// ============================================================

interface PageIndicatorProps {
  /** 전체 페이지 수 */
  total: number;
  /** 현재 페이지 인덱스 (0-based) */
  current: number;
  /** 페이지 선택 콜백 */
  onSelect?: (index: number) => void;
  /** 비활성화 여부 */
  disabled?: boolean;
  /** 스타일 변형 */
  variant?: 'dot' | 'bar';
  /** 추가 CSS 클래스 */
  className?: string;
}

// ============================================================
// Component
// ============================================================

const PageIndicator = ({
  total,
  current,
  onSelect,
  disabled = false,
  variant = 'dot',
  className,
}: PageIndicatorProps) => {
  // 단일 페이지면 표시하지 않음
  if (total <= 1) return null;

  return (
    <div className={clsx('flex items-center gap-2', className)}>
      {Array.from({ length: total }, (_, idx) => (
        <button
          key={idx}
          onClick={() => {
            if (!disabled && onSelect && idx !== current) {
              onSelect(idx);
            }
          }}
          disabled={disabled}
          className={clsx(
            'rounded-full transition-all',
            variant === 'bar'
              ? // Bar variant: 현재 페이지는 길고 파란색
                current === idx
                ? 'h-2 w-6 bg-blue-50'
                : 'h-2 w-2 bg-gray-30'
              : // Dot variant: 현재 페이지만 색상 다름
                current === idx
                ? 'h-2 w-2 bg-blue-50'
                : 'h-2 w-2 bg-gray-30',
            !disabled && 'cursor-pointer hover:opacity-80',
            disabled && 'cursor-not-allowed opacity-50',
          )}
          aria-label={`페이지 ${idx + 1}`}
          aria-current={current === idx ? 'page' : undefined}
        />
      ))}
    </div>
  );
};

export default PageIndicator;
