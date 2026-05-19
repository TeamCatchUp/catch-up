'use client';

// 검색 결과 정렬 드롭다운 (Figma 13640:52407) — 테두리·배경 없는 인라인 텍스트 드롭다운.
// 공통 DropdownMenu primitive 사용. 옵션: 최신순/오래된순.

import { useState } from 'react';

import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconDropdownUp from '@/public/icons/icon/dropdown_up.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';
import type { SortOrder } from '@/shared/utils/temporalRange';

const SORT_OPTIONS: ReadonlyArray<{ value: SortOrder; label: string }> = [
  { value: 'newest', label: '최신순' },
  { value: 'oldest', label: '오래된순' },
];

interface SortDropdownProps {
  value: SortOrder;
  onChange: (next: SortOrder) => void;
}

export default function SortDropdown({ value, onChange }: SortDropdownProps) {
  const [open, setOpen] = useState(false);
  const selectedLabel = SORT_OPTIONS.find((o) => o.value === value)?.label ?? '';

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="hover:bg-fill-interaction-hover flex h-8 max-w-37.5 min-w-9 cursor-pointer items-center gap-2 rounded-lg px-1 pb-2.5 transition-colors"
        >
          <span className="text-heading-small text-content-alternative flex-1 truncate text-left">
            {selectedLabel}
          </span>
          {open ? (
            <IconDropdownUp className="text-icon-alternative size-4 shrink-0" />
          ) : (
            <IconDropdownDown className="text-icon-alternative size-4 shrink-0" />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={4} className="min-w-0">
        {SORT_OPTIONS.map((option) => (
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
}
