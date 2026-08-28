import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import Pagination from '@/shared/components/ui/pagination';
import { cn } from '@/shared/utils/cn';

/** 한 쪽에 나열할 문서 수 후보(사용자 확정). */
const PAGE_SIZE_OPTIONS: readonly number[] = [10, 20, 30, 40, 50];

interface WikiSpaceTableFooterProps {
  pageSize: number;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** 쪽 크기 선택. 주면 표시가 드롭다운으로 열리고, 없으면 표시 그대로다. */
  onPageSizeChange?: (pageSize: number) => void;
}

const PAGE_SIZE_CONTROL_CLASS =
  'bg-fill-normal-normal border-line-normal-neutral flex h-9 items-center gap-1.5 rounded-lg border px-2.5';

/** 채널·폴더 목록 하단 바 — 페이지 크기 표시 + 가운데 정렬 페이지네이션. */
export default function WikiSpaceTableFooter({
  pageSize,
  currentPage,
  totalPages,
  onPageChange,
  onPageSizeChange,
}: WikiSpaceTableFooterProps) {
  const pageSizeContent = (
    <>
      <span className="text-body-small text-text-normal-neutral">{pageSize}</span>
      <IconDropdownDown aria-hidden className="text-icon-normal-neutral size-4 shrink-0" />
    </>
  );

  return (
    // 1fr/auto/1fr: 좌측 컨트롤 폭과 무관하게 페이지네이션을 바 중앙에 고정하기 위한 템플릿
    <div className="grid grid-cols-[1fr_auto_1fr] items-center">
      <div className="flex items-center gap-1 justify-self-start">
        {onPageSizeChange ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className={`${PAGE_SIZE_CONTROL_CLASS} cursor-pointer`}>
                {pageSizeContent}
              </button>
            </DropdownMenuTrigger>
            {/* 카드 폭은 트리거에 맞춘다 — 옵션이 숫자뿐이라 기본 최소폭(200)이 남는다 */}
            <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-0">
              {PAGE_SIZE_OPTIONS.map((option) => (
                <DropdownMenuItem
                  key={option}
                  onSelect={() => onPageSizeChange(option)}
                  className={cn('h-9', option === pageSize && 'bg-fill-normal-interaction-hover')}
                >
                  {option}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <span className={PAGE_SIZE_CONTROL_CLASS}>{pageSizeContent}</span>
        )}
        <span className="text-body-small text-text-normal-alternative">씩 나열</span>
      </div>

      <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />
    </div>
  );
}
