import ArrowLeft from '@/public/icons/icon/arrow_left.svg';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';
import { cn } from '@/shared/utils/cn';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const MAX_VISIBLE_PAGES = 5;

const getVisiblePages = (currentPage: number, totalPages: number) => {
  if (totalPages <= MAX_VISIBLE_PAGES) {
    return Array.from({ length: totalPages }, (_, idx) => idx + 1);
  }

  const half = Math.floor(MAX_VISIBLE_PAGES / 2);
  let start = Math.max(1, currentPage - half);
  let end = start + MAX_VISIBLE_PAGES - 1;

  if (end > totalPages) {
    end = totalPages;
    start = end - MAX_VISIBLE_PAGES + 1;
  }

  return Array.from({ length: end - start + 1 }, (_, idx) => start + idx);
};

/** 공통 숫자 페이지네이션 */
const Pagination = ({ currentPage, totalPages, onPageChange }: PaginationProps) => {
  const visiblePages = getVisiblePages(currentPage, totalPages);

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        aria-label="이전 페이지"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage <= 1}
        className="disabled:text-gray-20 rounded-md2 inline-flex size-7.5 cursor-pointer items-center justify-center text-gray-50 disabled:cursor-not-allowed"
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
                'text-body-small rounded-md2 flex size-7.5 cursor-pointer items-center justify-center tracking-tight',
                isActive ? 'bg-black/10 text-gray-80' : 'hover:bg-black/10 text-gray-50',
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
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages}
        className="disabled:text-gray-20 rounded-md2 inline-flex size-7.5 cursor-pointer items-center justify-center text-gray-50 disabled:cursor-not-allowed"
      >
        <ArrowRight className="size-6" />
      </button>
    </div>
  );
};

export default Pagination;
