import ArrowLeft from '@/public/icons/icon/arrow_left.svg';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';
import { cn } from '@/shared/utils/cn';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const MAX_VISIBLE_PAGES = 5;

// 현재 페이지가 속한 5-페이지 그룹의 시작(1, 6, 11, ...).
function getGroupStart(page: number): number {
  return Math.floor((page - 1) / MAX_VISIBLE_PAGES) * MAX_VISIBLE_PAGES + 1;
}

function getVisiblePages(currentPage: number, totalPages: number): number[] {
  const start = getGroupStart(currentPage);
  const end = Math.min(start + MAX_VISIBLE_PAGES - 1, totalPages);
  return Array.from({ length: end - start + 1 }, (_, idx) => start + idx);
}

/** 공통 숫자 페이지네이션 — 좌/우 화살표는 그룹 단위로 점프(1~5 → 6, 6~10 → 11). */
export default function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  const visiblePages = getVisiblePages(currentPage, totalPages);
  const groupStart = getGroupStart(currentPage);
  const groupEnd = Math.min(groupStart + MAX_VISIBLE_PAGES - 1, totalPages);
  const prevDisabled = groupStart <= 1;
  const nextDisabled = groupEnd >= totalPages;

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        aria-label="이전 페이지"
        onClick={() => onPageChange(groupStart - 1)}
        disabled={prevDisabled}
        className="disabled:text-content-assistive rounded-md2 text-icon-neutral inline-flex size-7.5 cursor-pointer items-center justify-center disabled:cursor-not-allowed"
      >
        <ArrowLeft className="size-6" />
      </button>

      <div className="flex items-center gap-1">
        {visiblePages.map((page) => {
          const isActive = page === currentPage;
          return (
            <button
              key={page}
              type="button"
              onClick={() => onPageChange(page)}
              className={cn(
                'text-body-small rounded-md2 flex size-7.5 cursor-pointer items-center justify-center',
                isActive ? 'bg-dim-black-10 text-content-normal' : 'hover:bg-dim-black-10 text-content-alternative',
              )}
            >
              {page}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        aria-label="다음 페이지"
        onClick={() => onPageChange(groupEnd + 1)}
        disabled={nextDisabled}
        className="disabled:text-content-assistive rounded-md2 text-icon-neutral inline-flex size-7.5 cursor-pointer items-center justify-center disabled:cursor-not-allowed"
      >
        <ArrowRight className="size-6" />
      </button>
    </div>
  );
}
