'use client';

import * as Popover from '@radix-ui/react-popover';
import { ReactNode } from 'react';

interface SearchOptionPopoverProps {
  trigger: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
}

export function SearchOptionPopover({ trigger, open, onOpenChange, children }: SearchOptionPopoverProps) {
  return (
    <Popover.Root open={open} onOpenChange={onOpenChange} modal={false}>
      <Popover.Trigger asChild>{trigger}</Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="start"
          sideOffset={8}
          className="border-neutral-5 shadow-dropdown-menu flex h-95 w-75 flex-col items-center gap-3 rounded-2xl bg-white py-2.5"
          onOpenAutoFocus={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => e.preventDefault()}
        >
          {children}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
