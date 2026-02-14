'use client';

import { ReactNode } from 'react';

import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';

interface FilterDropdownProps {
  trigger: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
}

export function FilterDropdown({ trigger, open, onOpenChange, children }: FilterDropdownProps) {
  return (
    <Popover open={open} onOpenChange={onOpenChange} modal={false}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>

      <PopoverContent
        side="bottom"
        align="start"
        sideOffset={8}
        className="border-neutral-5 flex h-95 w-75 flex-col items-center gap-3 rounded-2xl border bg-white p-0 py-2.5 shadow-[0px_2px_15px_rgba(0,0,0,0.15)]"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {children}
      </PopoverContent>
    </Popover>
  );
}
