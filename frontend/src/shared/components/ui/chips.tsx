'use client';

import { Children, cloneElement, type ComponentProps, isValidElement, type ReactNode } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

/* ── Chip ── */

const chipVariants = cva(
  'text-body-small inline-flex h-9 shrink-0 cursor-pointer items-center justify-center border font-medium transition-colors',
  {
    variants: {
      variant: {
        square: 'gap-1 rounded-lg px-2 py-1.5',
        capsule: 'gap-1.5 rounded-full px-3 py-1.5',
        outline: 'gap-1 rounded-full px-3 py-1.5',
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
          'bg-fill-normal-normal border-line-normal-neutral text-text-normal-normal hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed',
      },
      {
        variant: 'square',
        selected: true,
        class: 'bg-fill-primary-normal-assistive border-line-primary-normal text-text-primary-normal',
      },
      /* capsule */
      {
        variant: 'capsule',
        selected: false,
        class:
          'bg-fill-normal-normal border-line-normal-neutral text-text-normal-neutral hover:bg-fill-normal-interaction-hover hover:border-line-normal-normal active:bg-fill-normal-interaction-pressed active:border-line-normal-normal',
      },
      {
        variant: 'capsule',
        selected: true,
        class: 'bg-accent-green-lighten border-accent-green-neutral text-accent-green-default',
      },
      /* outline — selected에 border + bg, unselected는 텍스트만 노출하는 toggle 패턴 */
      {
        variant: 'outline',
        selected: false,
        class:
          'text-text-normal-alternative hover:bg-fill-normal-interaction-hover hover:text-text-normal-normal active:bg-fill-normal-interaction-pressed border-transparent bg-transparent',
      },
      {
        variant: 'outline',
        selected: true,
        class: 'bg-fill-normal-normal border-line-normal-strong text-text-normal-normal',
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

function Chip({ className, variant, selected = false, leadingIcon, trailingIcon, children, ref, ...props }: ChipProps) {
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
        const isSelected = mode === 'single' ? value === chipValue : Array.isArray(value) && value.includes(chipValue);

        return cloneElement(child, {
          selected: isSelected,
          onClick: () => handleClick(chipValue),
        });
      })}
    </div>
  );
}

export { Chip, ChipGroup, chipVariants };
