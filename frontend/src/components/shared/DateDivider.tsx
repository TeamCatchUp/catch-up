// ============================================================
// 날짜 구분선 컴포넌트
// 날짜를 중앙에 표시하는 가로 구분선
// ============================================================

'use client';

import clsx from 'clsx';

// ============================================================
// Types
// ============================================================

interface DateDividerProps {
  /** 표시할 날짜 (기본: 오늘) */
  date?: Date;
  /** 날짜 포맷 함수 */
  formatDate?: (date: Date) => string;
  /** 추가 CSS 클래스 */
  className?: string;
}

// ============================================================
// Default formatter
// ============================================================

const defaultFormatDate = (date: Date): string => {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${month}.${day}`;
};

// ============================================================
// Component
// ============================================================

const DateDivider = ({
  date = new Date(),
  formatDate = defaultFormatDate,
  className,
}: DateDividerProps) => {
  const formattedDate = formatDate(date);

  return (
    <div className={clsx('flex items-center justify-center gap-4', className)}>
      <div className="border-neutral-4 flex-1 border-t" />
      <span className="text-body-xsmall px-1.5 py-1 text-gray-50">{formattedDate}</span>
      <div className="border-neutral-4 flex-1 border-t" />
    </div>
  );
};

export default DateDivider;
