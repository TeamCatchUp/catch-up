import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import Pagination from '@/shared/components/ui/pagination';

interface WikiSpaceTableFooterProps {
  pageSize: number;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** 페이지 크기 선택 열기 — 옵션 시안이 없어 핸들러가 없으면 정적 표시로 그린다 */
  onPageSizeClick?: () => void;
}

const PAGE_SIZE_CONTROL_CLASS =
  'bg-fill-normal-normal border-line-normal-neutral flex h-9 items-center gap-1.5 rounded-lg border px-2.5';

/** 채널·폴더 목록 하단 바 — 페이지 크기 표시 + 가운데 정렬 페이지네이션. */
export default function WikiSpaceTableFooter({
  pageSize,
  currentPage,
  totalPages,
  onPageChange,
  onPageSizeClick,
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
        {onPageSizeClick ? (
          <button type="button" onClick={onPageSizeClick} className={`${PAGE_SIZE_CONTROL_CLASS} cursor-pointer`}>
            {pageSizeContent}
          </button>
        ) : (
          <span className={PAGE_SIZE_CONTROL_CLASS}>{pageSizeContent}</span>
        )}
        <span className="text-body-small text-text-normal-alternative">씩 나열</span>
      </div>

      <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />
    </div>
  );
}
