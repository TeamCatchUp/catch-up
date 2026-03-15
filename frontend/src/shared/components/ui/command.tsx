'use client';

import * as React from 'react';
import { Command as CommandPrimitive } from 'cmdk';

import TextfieldDelete from '@/public/icons/icon/TextfiledDelete.svg';
import { cn } from '@/shared/utils/cn';

const Command = React.forwardRef<
  React.ComponentRef<typeof CommandPrimitive>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive>
>(({ className, ...props }, ref) => (
  <CommandPrimitive
    ref={ref}
    className={cn('bg-fill-normal flex size-full flex-col overflow-hidden rounded-2xl', className)}
    {...props}
  />
));
Command.displayName = CommandPrimitive.displayName;

const CommandInput = React.forwardRef<
  React.ComponentRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(({ className, onValueChange, value: controlledValue, ...props }, ref) => {
  const [search, setSearch] = React.useState('');

  const value = controlledValue ?? search;

  const handleValueChange = (v: string) => {
    setSearch(v);
    onValueChange?.(v);
  };

  const handleClear = () => {
    setSearch('');
    onValueChange?.('');
  };

  return (
    <div
      className="bg-fill-strong focus-within:border-edge-primary flex min-h-[40px] items-center gap-1.5 rounded-lg border border-transparent px-3 py-2"
      cmdk-input-wrapper=""
    >
      <CommandPrimitive.Input
        ref={ref}
        value={value}
        onValueChange={handleValueChange}
        className={cn(
          'text-body-small text-content-normal placeholder:text-content-assistive flex w-full bg-transparent tracking-tight outline-none disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      />
      {value && (
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleClear}
          className="text-icon-assistive shrink-0 cursor-pointer"
        >
          <TextfieldDelete className="size-5" />
        </button>
      )}
    </div>
  );
});
CommandInput.displayName = CommandPrimitive.Input.displayName;

const CommandList = React.forwardRef<
  React.ComponentRef<typeof CommandPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.List
    ref={ref}
    className={cn('max-h-[300px] overflow-x-hidden overflow-y-auto px-1.5 py-2', className)}
    {...props}
  />
));
CommandList.displayName = CommandPrimitive.List.displayName;

const CommandEmpty = React.forwardRef<
  React.ComponentRef<typeof CommandPrimitive.Empty>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>
>((props, ref) => (
  <CommandPrimitive.Empty ref={ref} className="text-body-small text-content-alternative py-6 text-center" {...props} />
));
CommandEmpty.displayName = CommandPrimitive.Empty.displayName;

const CommandGroup = React.forwardRef<
  React.ComponentRef<typeof CommandPrimitive.Group>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Group>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Group
    ref={ref}
    className={cn(
      '[&_[cmdk-group-heading]]:text-label-xsmall [&_[cmdk-group-heading]]:text-content-alternative overflow-hidden [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5',
      className,
    )}
    {...props}
  />
));
CommandGroup.displayName = CommandPrimitive.Group.displayName;

const CommandSeparator = React.forwardRef<
  React.ComponentRef<typeof CommandPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Separator ref={ref} className={cn('bg-edge-neutral mx-1 my-1 h-px', className)} {...props} />
));
CommandSeparator.displayName = CommandPrimitive.Separator.displayName;

const CommandItem = React.forwardRef<
  React.ComponentRef<typeof CommandPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Item
    ref={ref}
    className={cn(
      'text-body-small text-content-normal data-[selected=true]:bg-fill-interaction-hover relative flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 outline-none select-none data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50',
      className,
    )}
    {...props}
  />
));
CommandItem.displayName = CommandPrimitive.Item.displayName;

export { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator };
