'use client';

import * as React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';

import UnfoldMoreIcon from '@/public/icons/icon/unfold_more.svg';
import { cn } from '@/shared/utils/cn';

const Select = SelectPrimitive.Root;
const SelectGroup = SelectPrimitive.Group;
const SelectValue = SelectPrimitive.Value;

const SelectTrigger = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      'border-edge-neutral text-body-small text-content-normal hover:bg-fill-interaction-hover data-[state=open]:bg-fill-interaction-pressed data-[state=open]:border-edge-normal data-placeholder:text-content-assistive bg-fill-normal flex w-full cursor-pointer items-center justify-between gap-3 rounded-lg border px-2.5 py-1.5 transition-colors focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1',
      className,
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <UnfoldMoreIcon className="text-icon-neutral size-6 shrink-0" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
));
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName;

const SelectContent = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = 'popper', ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      className={cn(
        'border-edge-normal shadow-dropdown-menu data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 bg-fill-normal relative z-dropdown max-h-96 min-w-32 overflow-hidden rounded-lg border',
        position === 'popper' &&
          'data-[side=bottom]:translate-y-0.5 data-[side=left]:-translate-x-0.5 data-[side=right]:translate-x-0.5 data-[side=top]:-translate-y-0.5',
        className,
      )}
      position={position}
      {...props}
    >
      <SelectPrimitive.Viewport
        className={cn(
          'space-y-1 p-1',
          position === 'popper' &&
            'h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]',
        )}
      >
        {children}
      </SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
));
SelectContent.displayName = SelectPrimitive.Content.displayName;

const SelectItem = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      'text-body-small text-content-normal data-highlighted:bg-fill-interaction-hover relative flex w-full cursor-pointer items-center rounded-lg px-2 py-2 outline-none select-none data-disabled:pointer-events-none data-disabled:opacity-50',
      className,
    )}
    {...props}
  >
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
));
SelectItem.displayName = SelectPrimitive.Item.displayName;

const SelectSeparator = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.Separator ref={ref} className={cn('bg-edge-neutral mx-1 my-1 h-px', className)} {...props} />
));
SelectSeparator.displayName = SelectPrimitive.Separator.displayName;

export { Select, SelectContent, SelectGroup, SelectItem, SelectSeparator, SelectTrigger, SelectValue };
