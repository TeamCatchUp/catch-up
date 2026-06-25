'use client';

import { useState } from 'react';
import { useTheme } from 'next-themes';

import IconCheck from '@/public/icons/icon/check.svg';
import DropdownDown from '@/public/icons/icon/dropdown_down.svg';
import DropdownUp from '@/public/icons/icon/dropdown_up.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import { THEME_OPTIONS } from '../../constants/preferencesConfig';
import SectionBar from '../SectionBar';

export default function DisplayModeSection() {
  const { theme, setTheme } = useTheme();
  const currentTheme = theme ?? 'system';
  const [open, setOpen] = useState(false);
  const selectedLabel = THEME_OPTIONS.find((o) => o.value === currentTheme)?.label ?? '시스템';

  return (
    <div className="flex flex-col">
      <SectionBar title="화면 모드" />
      <div className="flex w-full items-center gap-5 px-4 py-3">
        <div className="flex w-full flex-col gap-1.5">
          <span className="text-heading-small text-text-normal-normal">화면 모드</span>
          <span className="text-label-small text-text-normal-alternative">이 기기에서 화면 테마를 선택해주세요.</span>
        </div>

        <DropdownMenu open={open} onOpenChange={setOpen}>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex max-w-37.5 min-w-9 shrink-0 cursor-pointer items-center gap-1 rounded-lg px-2 py-1"
            >
              <span className="text-body-small text-text-normal-neutral whitespace-nowrap">{selectedLabel}</span>
              {open ? (
                <DropdownUp className="text-icon-normal-normal size-4.5 shrink-0" />
              ) : (
                <DropdownDown className="text-icon-normal-normal size-4.5 shrink-0" />
              )}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" sideOffset={4} className="w-50 min-w-0">
            {THEME_OPTIONS.map((option) => (
              <DropdownMenuItem
                key={option.value}
                onClick={() => setTheme(option.value)}
                className={cn(currentTheme === option.value && 'bg-fill-normal-interaction-hover')}
              >
                <span className="flex-1">{option.label}</span>
                {currentTheme === option.value && <IconCheck className="text-icon-normal-normal size-6" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
