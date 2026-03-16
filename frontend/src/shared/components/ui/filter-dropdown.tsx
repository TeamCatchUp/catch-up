'use client';

import { useMemo, useState } from 'react';

import DropdownDown from '@/public/icons/icon/dropdown_down.svg';
import DropdownUp from '@/public/icons/icon/dropdown_up.svg';
import { cn } from '@/shared/utils/cn';

import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './dropdown-menu';

/** 드롭다운 필터 옵션 항목 */
export interface FilterOption<T extends string> {
  value: T;
  label: string;
}

interface FilterDropdownProps<T extends string> {
  options: readonly FilterOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

/** 정렬·기간 등 필터 옵션을 선택하는 제네릭 드롭다운 */
const FilterDropdown = <T extends string>({ options, value, onChange }: FilterDropdownProps<T>) => {
  const [open, setOpen] = useState(false);

  const selectedLabel = useMemo(() => options.find((o) => o.value === value)?.label ?? '', [options, value]);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="border-edge-neutral hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed bg-fill-normal flex h-9 max-w-[150px] min-w-9 cursor-pointer items-center gap-1 rounded-lg border px-2.5 py-2"
        >
          <span className="text-body-small text-content-neutral whitespace-nowrap">{selectedLabel}</span>
          {open ? (
            <DropdownUp className="text-icon-neutral size-[18px] shrink-0" />
          ) : (
            <DropdownDown className="text-icon-neutral size-[18px] shrink-0" />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" sideOffset={4} className="w-[140px] min-w-0">
        {options.map((option) => (
          <DropdownMenuItem
            key={option.value}
            onClick={() => onChange(option.value)}
            className={cn(option.value === value && 'bg-fill-strong')}
          >
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default FilterDropdown;
