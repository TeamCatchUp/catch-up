'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

const buttonVariants = cva(
  'inline-flex shrink-0 cursor-pointer items-center justify-center tracking-tight transition-colors focus-visible:outline-none disabled:pointer-events-none',
  {
    variants: {
      variant: {
        /* ── Icon Buttons ── */
        'icon-solid-blue': 'hover:bg-blue-55 active:bg-blue-60 disabled:bg-blue-10 rounded-lg bg-blue-50 text-white',
        'icon-outline-gray':
          'border-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 disabled:border-neutral-2 disabled:text-gray-20 text-gray-70 rounded-lg border bg-white',
        'icon-only-gray':
          'hover:text-gray-70 hover:bg-neutral-2 active:text-gray-70 active:bg-neutral-3 disabled:text-gray-20 rounded-lg text-gray-50',
        'icon-only-blue':
          'hover:bg-blue-5 active:bg-blue-10 active:text-blue-60 disabled:text-gray-20 rounded-full text-blue-50',

        /* ── Box Buttons ── */
        'box-solid-primary': 'hover:bg-blue-55 active:bg-blue-60 disabled:bg-blue-10 rounded-lg bg-blue-50 text-white',
        'box-outline-gray':
          'border-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 disabled:bg-neutral-1 disabled:text-gray-30 text-gray-70 rounded-lg border bg-white',
        'box-outline-blue':
          'border-blue-40 hover:bg-blue-5 active:bg-blue-10 disabled:bg-neutral-1 disabled:text-gray-30 disabled:border-neutral-2 bg-blue-1 rounded-lg border text-blue-50',

        /* ── Capsule Buttons ── */
        'capsule-solid-primary':
          'hover:bg-blue-55 active:bg-blue-60 disabled:bg-blue-10 rounded-full bg-blue-50 text-white',
        'capsule-outline-mono':
          'border-neutral-4 hover:bg-neutral-2 active:border-neutral-3 active:bg-neutral-3 disabled:border-neutral-4 disabled:bg-neutral-1 disabled:text-gray-30 rounded-full border bg-white',
        'capsule-outline-blue':
          'border-blue-30 bg-blue-1 text-blue-50 hover:bg-blue-5 active:bg-blue-5 active:border-blue-45 disabled:text-gray-30 disabled:bg-neutral-1 disabled:border-neutral-2 rounded-full border',
        'capsule-solid-purple': 'bg-violet-5 rounded-full',
        'capsule-solid-light-blue': 'bg-light-blue-5 rounded-full',

        /* ── Text Buttons ── */
        'text-primary-blue': 'hover:bg-blue-5 active:bg-blue-5 rounded-full text-blue-50',
        'text-secondary-mono': 'hover:bg-neutral-2 active:bg-neutral-3 disabled:text-gray-20 text-gray-70 rounded-full',

        /* ── FAB ── */
        'fab-primary': 'bg-neutral-80 shadow-button rounded-full text-white',
        'fab-secondary':
          'hover:bg-neutral-2 active:bg-neutral-3 text-gray-70 shadow-button border-neutral-3 rounded-full border bg-white',
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
        variant: ['box-solid-primary', 'box-outline-gray', 'box-outline-blue'],
        size: 'lg',
        class: 'text-body-medium gap-1 px-4 py-1.5',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray', 'box-outline-blue'],
        size: 'md',
        class: 'text-body-small gap-1 px-2.5 py-1.5',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray', 'box-outline-blue'],
        size: 'sm',
        class: 'text-body-xsmall gap-1 px-2 py-1',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray', 'box-outline-blue'],
        size: 'xs',
        class: 'rounded-md2 text-body-xsmall gap-1 px-1.5 py-1',
      },

      /* ── Capsule sizes (Figma: lg + sm only) ── */
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
