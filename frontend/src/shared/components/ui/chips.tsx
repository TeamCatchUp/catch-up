'use client';

import { Children, cloneElement, type ComponentProps, isValidElement, type ReactNode } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

/* ── Chip ── */

const chipVariants = cva(
  'inline-flex h-9 items-center justify-center border text-body-small font-medium cursor-pointer transition-colors shrink-0',
  {
    variants: {
      variant: {
        square: 'rounded-lg px-2 py-1.5 gap-1',
        capsule: 'rounded-full px-3 py-1.5 gap-1.5',
      },
      selected: {
        true: '',
        false: '',
      },
    },
    compoundVariants: [
      /* square */
      {
        variant: 'square',
        selected: false,
        class:
          'bg-fill-normal border-edge-neutral text-content-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed',
      },
      {
        variant: 'square',
        selected: true,
        class: 'bg-fill-primary-assistive border-edge-primary text-content-primary',
      },
      /* capsule */
      {
        variant: 'capsule',
        selected: false,
        class:
          'bg-fill-normal border-edge-neutral text-content-neutral hover:bg-fill-interaction-hover hover:border-edge-normal active:bg-fill-interaction-pressed active:border-edge-normal',
      },
      {
        variant: 'capsule',
        selected: true,
        class: 'bg-accent-green-lighten border-accent-green-neutral text-accent-green',
      },
    ],
    defaultVariants: {
      variant: 'square',
      selected: false,
    },
  },
);

type ChipProps = ComponentProps<'button'> &
  Omit<VariantProps<typeof chipVariants>, 'selected'> & {
    selected?: boolean;
    leadingIcon?: ReactNode;
    trailingIcon?: ReactNode;
    value?: string;
  };

function Chip({
  className,
  variant,
  selected = false,
  leadingIcon,
  trailingIcon,
  children,
  ref,
  ...props
}: ChipProps) {
  return (
    <button
      ref={ref}
      type="button"
      className={cn(chipVariants({ variant, selected, className }))}
      data-selected={selected}
      {...props}
    >
      {leadingIcon && <span className="shrink-0 [&>svg]:h-5 [&>svg]:w-5">{leadingIcon}</span>}
      <span className="overflow-hidden text-ellipsis whitespace-nowrap">{children}</span>
      {trailingIcon && <span className="shrink-0 [&>svg]:h-5 [&>svg]:w-5">{trailingIcon}</span>}
    </button>
  );
}

/* ── ChipGroup ── */

interface ChipGroupProps {
  mode: 'single' | 'multi';
  value: string | string[];
  onChange: (value: string | string[]) => void;
  children: ReactNode;
  className?: string;
}

function ChipGroup({ mode, value, onChange, children, className }: ChipGroupProps) {
  const handleClick = (chipValue: string) => {
    if (mode === 'single') {
      onChange(value === chipValue ? '' : chipValue);
    } else {
      const arr = Array.isArray(value) ? value : [];
      onChange(arr.includes(chipValue) ? arr.filter((v) => v !== chipValue) : [...arr, chipValue]);
    }
  };

  return (
    <div className={cn('flex flex-wrap gap-2.5', className)}>
      {Children.map(children, (child) => {
        if (!isValidElement<ChipProps>(child)) return child;

        const chipValue = child.props.value ?? '';
        const isSelected =
          mode === 'single' ? value === chipValue : Array.isArray(value) && value.includes(chipValue);

        return cloneElement(child, {
          selected: isSelected,
          onClick: () => handleClick(chipValue),
        });
      })}
    </div>
  );
}

export { Chip, ChipGroup, chipVariants };
