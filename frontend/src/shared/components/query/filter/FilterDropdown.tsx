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
        className="flex h-95 w-75 flex-col items-center gap-3 rounded-2xl bg-white py-2.5"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {children}
      </PopoverContent>
    </Popover>
  );
}
