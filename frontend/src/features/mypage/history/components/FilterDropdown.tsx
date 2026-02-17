'use client';

import { useMemo, useState } from 'react';

import DropdownDown from '@/public/icons/icon/dropdown_down.svg';
import DropdownUp from '@/public/icons/icon/dropdown_up.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import type { HistoryFilterOption } from '../types/models';

/** {@link HistoryFilterDropdown} 컴포넌트 Props */
interface HistoryFilterDropdownProps<T extends string> {
  /** 드롭다운에 표시할 옵션 목록 */
  options: readonly HistoryFilterOption<T>[];
  /** 현재 선택된 값 */
  value: T;
  /** 옵션 선택 시 호출되는 콜백 */
  onChange: (value: T) => void;
}

/**
 * 히스토리 필터용 드롭다운 컴포넌트.
 * 정렬·기간 등 필터 옵션을 선택할 수 있는 제네릭 드롭다운이다.
 */
const HistoryFilterDropdown = <T extends string>({ options, value, onChange }: HistoryFilterDropdownProps<T>) => {
  const [open, setOpen] = useState(false);

  const selectedLabel = useMemo(() => options.find((option) => option.value === value)?.label ?? '', [options, value]);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            'border-neutral-3 hover:bg-neutral-2 active:bg-neutral-3 flex h-9 max-w-[150px] min-w-9 cursor-pointer items-center gap-1 rounded-lg border bg-white px-2.5 py-2',
          )}
        >
          <span className="text-body-small text-gray-70 whitespace-nowrap">{selectedLabel}</span>
          {open ? (
            <DropdownUp className="text-gray-70 size-[18px] shrink-0" />
          ) : (
            <DropdownDown className="text-gray-70 size-[18px] shrink-0" />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" sideOffset={4} className="w-[140px] min-w-0">
        {options.map((option) => (
          <DropdownMenuItem
            key={option.value}
            onClick={() => onChange(option.value)}
            className={cn(option.value === value && 'bg-neutral-1')}
          >
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default HistoryFilterDropdown;
