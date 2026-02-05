import IconBack from '@/public/icons/icon/arrow_left2.svg';
import IconCheckOn from '@/public/icons/icon/checkbox_checked.svg';
import IconCheckOff from '@/public/icons/icon/checkbox_unchecked.svg';
import type { ReactNode } from 'react';

interface ExplorerHeaderProps {
  title: ReactNode;
  showBackButton: boolean;
  onBack: () => void;
  showSelectAll?: boolean;
  isAllSelected?: boolean;
  onSelectAll?: (e: React.MouseEvent) => void;
  selectAllLabel?: string;
}

export const ExplorerHeader = ({
  title,
  showBackButton,
  onBack,
  showSelectAll = false,
  isAllSelected = false,
  onSelectAll,
  selectAllLabel = '전체 범위 적용',
}: ExplorerHeaderProps) => {
  return (
    <div className="flex flex-[1_0_0] items-center gap-1.5">
      {showBackButton && (
        <button
          type="button"
          className="hover:bg-neutral-3 flex h-7 w-7 items-center justify-center rounded-full p-0.5"
          onMouseDown={(e) => e.preventDefault()}
          onClick={onBack}
        >
          <IconBack className="text-gray-90 h-5 w-5" />
        </button>
      )}

      <div className="text-body-medium text-gray-80 truncate select-none">{title}</div>

      {showSelectAll && onSelectAll && (
        <button
          type="button"
          className="hover:bg-neutral-1 ml-1 flex cursor-pointer items-center gap-0.5 rounded px-1 py-0.5"
          onMouseDown={(e) => e.preventDefault()}
          onClick={onSelectAll}
        >
          {isAllSelected ? (
            <IconCheckOn className="h-5 w-5 text-blue-50" />
          ) : (
            <IconCheckOff className="text-gray-30 h-5 w-5" />
          )}
          <div className="text-body-xsmall text-gray-70 select-none whitespace-nowrap">{selectAllLabel}</div>
        </button>
      )}
    </div>
  );
};
