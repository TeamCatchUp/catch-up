'use client';

import * as React from 'react';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';

import CheckIcon from '@/public/icons/icon/check.svg';
import { cn } from '@/shared/utils/cn';

const Checkbox = React.forwardRef<
  React.ComponentRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      'peer border-edge-neutral hover:border-edge-normal size-5 shrink-0 cursor-pointer rounded-md border bg-fill-normal transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-blue-50 data-[state=checked]:bg-blue-50',
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className="flex items-center justify-center text-white">
      <CheckIcon className="size-3.5" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

export { Checkbox };
