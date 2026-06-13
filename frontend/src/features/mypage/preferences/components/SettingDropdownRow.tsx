'use client';

import { useState } from 'react';

import DropdownDown from '@/public/icons/icon/dropdown_down.svg';
import DropdownUp from '@/public/icons/icon/dropdown_up.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

interface SettingDropdownRowProps {
  label: string;
  description: string;
  options: readonly { readonly value: string; readonly label: string }[];
  value: string;
  onChange: (value: string) => void;
}

export default function SettingDropdownRow({ label, description, options, value, onChange }: SettingDropdownRowProps) {
  const [open, setOpen] = useState(false);
  const selectedLabel = options.find((o) => o.value === value)?.label ?? '';

  return (
    <div className="border-line-normal-neutral flex w-full items-center gap-5 border-b py-3">
      <div className="flex w-full flex-col gap-1.5">
        <span className="text-heading-small text-text-normal-normal">{label}</span>
        <span className="text-label-small text-text-normal-alternative">{description}</span>
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
          {options.map((option) => (
            <DropdownMenuItem
              key={option.value}
              onClick={() => onChange(option.value)}
              className={cn(value === option.value && 'bg-fill-normal-strong')}
            >
              {option.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
