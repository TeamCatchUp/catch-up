'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

const buttonVariants = cva(
  'inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap transition-colors focus-visible:outline-none disabled:pointer-events-none',
  {
    variants: {
      variant: {
        /* ── Icon Buttons ── */
        'icon-solid-blue':
          'hover:bg-fill-primary-normal-interaction-hover active:bg-fill-primary-normal-interaction-pressed disabled:bg-fill-primary-normal-interaction-inactive bg-fill-primary-normal-normal rounded-lg text-white',
        'icon-outline-gray':
          'border-line-normal-neutral hover:border-line-normal-normal hover:bg-fill-normal-interaction-hover active:border-line-normal-strong active:bg-fill-normal-interaction-pressed disabled:border-line-normal-assistive disabled:text-text-normal-assistive text-icon-normal-normal bg-fill-normal-normal rounded-lg border',
        'icon-only-gray':
          'hover:text-icon-normal-normal hover:bg-fill-normal-interaction-hover active:text-icon-normal-normal active:bg-fill-normal-interaction-pressed disabled:text-text-normal-assistive text-icon-normal-neutral rounded-lg',
        'icon-only-blue':
          'hover:bg-fill-primary-normal-interaction-hover-assistive active:bg-fill-primary-normal-interaction-hover-assistive active:text-icon-primary-strong disabled:text-text-normal-assistive text-icon-primary-normal rounded-full',

        /* ── Box Buttons ── */
        'box-solid-primary':
          'hover:bg-fill-primary-normal-interaction-hover active:bg-fill-primary-normal-interaction-pressed disabled:bg-fill-normal-interaction-inactive disabled:text-text-normal-assistive disabled:[&_svg]:text-icon-normal-assistive bg-fill-primary-normal-normal rounded-lg text-white',
        'box-outline-gray':
          'border-line-normal-neutral hover:border-line-normal-normal hover:bg-fill-normal-interaction-hover active:border-line-normal-strong active:bg-fill-normal-interaction-pressed disabled:bg-fill-normal-interaction-inactive disabled:border-line-normal-normal disabled:text-text-normal-assistive disabled:[&_svg]:text-icon-normal-assistive text-icon-normal-normal bg-fill-normal-normal rounded-lg border',
        'box-outline-blue':
          'border-line-primary-normal hover:bg-fill-primary-normal-interaction-hover-assistive active:bg-fill-primary-normal-interaction-hover-assistive disabled:bg-fill-normal-interaction-inactive disabled:text-text-normal-assistive disabled:border-line-normal-normal disabled:[&_svg]:text-icon-normal-assistive bg-fill-primary-normal-assistive text-text-primary-normal rounded-lg border',
        'box-soft-primary':
          'bg-fill-primary-normal-neutral border-line-normal-neutral text-text-primary-normal hover:bg-fill-primary-normal-interaction-hover-assistive active:bg-fill-primary-normal-interaction-hover-assistive disabled:bg-fill-normal-interaction-inactive disabled:border-line-normal-normal disabled:text-text-normal-assistive disabled:[&_svg]:text-icon-normal-assistive rounded-lg border',

        /* ── Capsule Buttons ── */
        'capsule-solid-primary':
          'hover:bg-fill-primary-normal-interaction-hover active:bg-fill-primary-normal-interaction-pressed disabled:bg-fill-normal-interaction-inactive disabled:text-text-normal-assistive disabled:[&_svg]:text-icon-normal-assistive bg-fill-primary-normal-normal rounded-full text-white',
        'capsule-outline-mono':
          'border-line-normal-normal hover:bg-fill-normal-interaction-hover active:border-line-normal-neutral active:bg-fill-normal-interaction-pressed disabled:border-line-normal-normal disabled:bg-fill-normal-interaction-inactive disabled:text-text-normal-assistive disabled:[&_svg]:text-icon-normal-assistive bg-fill-normal-normal rounded-full border',
        'capsule-outline-blue':
          'border-line-primary-normal bg-fill-primary-normal-assistive text-text-primary-normal hover:bg-fill-primary-normal-interaction-hover-assistive active:bg-fill-primary-normal-interaction-hover-assistive active:border-line-primary-strong disabled:text-text-normal-assistive disabled:bg-fill-normal-interaction-inactive disabled:border-line-normal-normal disabled:[&_svg]:text-icon-normal-assistive rounded-full border',
        'capsule-solid-purple': 'bg-accent-violet-neutral rounded-full',
        'capsule-solid-light-blue': 'bg-accent-light-blue-lighten rounded-full',

        /* ── Text Buttons ── */
        'text-primary-blue':
          'hover:bg-fill-primary-normal-interaction-hover-assistive active:bg-fill-primary-normal-interaction-hover-assistive text-text-primary-normal rounded-full',
        'text-secondary-mono':
          'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed disabled:text-text-normal-assistive text-icon-normal-normal rounded-full',

        /* ── FAB ── */
        'fab-primary':
          'bg-accent-black-lighten hover:bg-accent-black-default active:bg-accent-black-default shadow-button text-icon-normal-inverse rounded-full',
        'fab-secondary':
          'hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed text-icon-normal-normal shadow-button border-line-normal-neutral bg-fill-normal-normal rounded-full border',
      },
      size: {
        lg: '',
        md: '',
        sm: '',
        xs: '',
      },
    },
    compoundVariants: [
      /* ── Icon sizes ── */
      {
        variant: ['icon-solid-blue', 'icon-outline-gray', 'icon-only-gray', 'icon-only-blue'],
        size: 'lg',
        class: 'p-2',
      },
      {
        variant: ['icon-solid-blue', 'icon-outline-gray', 'icon-only-gray', 'icon-only-blue'],
        size: 'md',
        class: 'p-1.5',
      },
      {
        variant: ['icon-solid-blue', 'icon-outline-gray'],
        size: 'sm',
        class: 'p-1',
      },
      {
        variant: 'icon-outline-gray',
        size: 'sm',
        class: 'rounded-md2',
      },
      {
        variant: ['icon-only-gray', 'icon-only-blue'],
        size: 'sm',
        class: 'rounded-full p-0.5',
      },
      {
        variant: ['icon-solid-blue', 'icon-outline-gray', 'icon-only-gray', 'icon-only-blue'],
        size: 'xs',
        class: 'p-px',
      },
      {
        variant: ['icon-only-gray', 'icon-only-blue'],
        size: 'xs',
        class: 'rounded-full',
      },

      /* ── Box sizes ── */
      {
        variant: ['box-solid-primary', 'box-outline-gray', 'box-outline-blue', 'box-soft-primary'],
        size: 'lg',
        class: 'text-body-medium gap-1 px-4 py-1.5',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray', 'box-outline-blue', 'box-soft-primary'],
        size: 'md',
        class: 'text-body-small gap-1 px-2.5 py-1.5',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray', 'box-outline-blue', 'box-soft-primary'],
        size: 'sm',
        class: 'text-body-xsmall gap-1 px-2 py-1',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray', 'box-outline-blue', 'box-soft-primary'],
        size: 'xs',
        class: 'rounded-md2 text-body-xsmall gap-1 px-1.5 py-1',
      },

      /* ── Capsule sizes (lg + sm only) ── */
      {
        variant: [
          'capsule-solid-primary',
          'capsule-outline-mono',
          'capsule-outline-blue',
          'capsule-solid-purple',
          'capsule-solid-light-blue',
        ],
        size: 'lg',
        class: 'text-heading-medium gap-1 px-4 py-1.5',
      },
      {
        variant: [
          'capsule-solid-primary',
          'capsule-outline-mono',
          'capsule-outline-blue',
          'capsule-solid-purple',
          'capsule-solid-light-blue',
        ],
        size: 'md',
        class: 'text-body-small gap-1 px-3 py-1.5',
      },
      {
        variant: [
          'capsule-solid-primary',
          'capsule-outline-mono',
          'capsule-outline-blue',
          'capsule-solid-purple',
          'capsule-solid-light-blue',
        ],
        size: 'sm',
        class: 'text-body-small gap-1 px-3 py-1.5',
      },
      {
        variant: [
          'capsule-solid-primary',
          'capsule-outline-mono',
          'capsule-outline-blue',
          'capsule-solid-purple',
          'capsule-solid-light-blue',
        ],
        size: 'xs',
        class: 'text-body-small gap-1 px-3 py-1.5',
      },

      /* ── Text sizes ── */
      {
        variant: ['text-primary-blue', 'text-secondary-mono'],
        size: 'lg',
        class: 'text-heading-medium gap-1.5 px-3 py-1.5',
      },
      {
        variant: ['text-primary-blue', 'text-secondary-mono'],
        size: 'md',
        class: 'text-body-small gap-0.5 px-1.5 py-1',
      },
      {
        variant: ['text-primary-blue', 'text-secondary-mono'],
        size: 'sm',
        class: 'text-body-xsmall gap-1 px-1.5 py-1',
      },
      {
        variant: ['text-primary-blue', 'text-secondary-mono'],
        size: 'xs',
        class: 'text-body-xsmall gap-1 px-1.5 py-1',
      },

      /* ── FAB ── */
      {
        variant: ['fab-primary', 'fab-secondary'],
        size: 'lg',
        class: 'p-1.5',
      },
      {
        variant: ['fab-primary', 'fab-secondary'],
        size: 'md',
        class: 'p-1.5',
      },
      {
        variant: ['fab-primary', 'fab-secondary'],
        size: 'sm',
        class: 'p-1.5',
      },
      {
        variant: ['fab-primary', 'fab-secondary'],
        size: 'xs',
        class: 'p-1.5',
      },
    ],
    defaultVariants: {
      variant: 'box-solid-primary',
      size: 'md',
    },
  },
);

type ButtonProps = React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : 'button';

  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

export { Button, buttonVariants };
