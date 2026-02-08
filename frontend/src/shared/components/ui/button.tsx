'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva,type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center shrink-0 tracking-tight transition-colors focus-visible:outline-none disabled:pointer-events-none cursor-pointer',
  {
    variants: {
      variant: {
        /* ── Icon Buttons ── */
        'icon-solid-blue':
          'bg-blue-50 hover:bg-blue-55 active:bg-blue-60 disabled:bg-blue-10 rounded-lg text-white',
        'icon-outline-gray':
          'border border-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 disabled:border-neutral-2 disabled:text-gray-20 text-gray-70 rounded-lg bg-white',
        'icon-only-gray':
          'hover:text-gray-70 hover:bg-neutral-2 active:text-gray-70 active:bg-neutral-3 disabled:text-gray-20 text-gray-50 rounded-lg',
        'icon-only-blue':
          'hover:bg-blue-5 active:bg-blue-10 active:text-blue-60 disabled:text-gray-20 text-blue-50 rounded-full',

        /* ── Box Buttons ── */
        'box-solid-primary':
          'bg-blue-50 hover:bg-blue-55 active:bg-blue-60 disabled:bg-blue-10 rounded-lg text-white',
        'box-outline-gray':
          'border border-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 active:border-neutral-5 active:bg-neutral-3 disabled:bg-neutral-1 disabled:text-gray-30 rounded-lg bg-white text-gray-70',

        /* ── Capsule Buttons ── */
        'capsule-solid-primary':
          'bg-blue-50 hover:bg-blue-55 active:bg-blue-60 disabled:bg-blue-10 rounded-full text-white',
        'capsule-outline-mono':
          'border border-neutral-4 hover:bg-neutral-2 active:border-neutral-3 active:bg-neutral-3 disabled:border-neutral-4 disabled:bg-neutral-1 disabled:text-gray-30 rounded-full bg-white',
        'capsule-outline-blue':
          'border border-blue-30 bg-blue-1 hover:bg-blue-5 active:bg-blue-5 active:border-blue-45 disabled:text-gray-30 disabled:bg-neutral-1 disabled:border-neutral-2 rounded-full',
        'capsule-outline-purple': 'bg-violet-5 rounded-full',
        'capsule-outline-light-blue': 'bg-light-blue-5 rounded-full',

        /* ── Text Buttons ── */
        'text-primary-blue':
          'hover:bg-blue-5 active:bg-blue-5 rounded-full text-blue-50',
        'text-secondary-mono':
          'hover:bg-neutral-2 active:bg-neutral-3 rounded-full text-gray-70',

        /* ── FAB ── */
        'fab-primary': 'bg-neutral-80 rounded-full text-white shadow-button',
        'fab-secondary':
          'bg-white hover:bg-neutral-2 active:bg-neutral-3 rounded-full text-gray-70 shadow-button border border-neutral-3',
      },
      size: {
        lg: '',
        md: '',
        sm: '',
        xs: '',
      },
    },
    compoundVariants: [
      /* ── Icon sizes (square) ── */
      {
        variant: ['icon-solid-blue', 'icon-outline-gray', 'icon-only-gray', 'icon-only-blue'],
        size: 'lg',
        class: 'size-10 p-1.5',
      },
      {
        variant: ['icon-solid-blue', 'icon-outline-gray', 'icon-only-gray', 'icon-only-blue'],
        size: 'md',
        class: 'size-9 p-[5px]',
      },
      {
        variant: ['icon-solid-blue', 'icon-outline-gray', 'icon-only-gray', 'icon-only-blue'],
        size: 'sm',
        class: 'size-[30px] p-[3px]',
      },
      {
        variant: ['icon-solid-blue', 'icon-outline-gray', 'icon-only-gray', 'icon-only-blue'],
        size: 'xs',
        class: 'size-[22px] p-px',
      },

      /* ── Box sizes ── */
      {
        variant: ['box-solid-primary', 'box-outline-gray'],
        size: 'lg',
        class: 'h-10 min-w-10 px-4 py-1.5 gap-1 text-body-medium',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray'],
        size: 'md',
        class: 'h-9 min-w-9 px-2.5 py-1.5 gap-1 text-heading-small',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray'],
        size: 'sm',
        class: 'h-[30px] min-w-[30px] px-2 py-1 gap-1 text-body-xsmall',
      },
      {
        variant: ['box-solid-primary', 'box-outline-gray'],
        size: 'xs',
        class: 'h-7 min-w-7 px-1.5 py-0.5 gap-0.5 text-body-xsmall',
      },

      /* ── Capsule sizes (Figma: lg + sm only) ── */
      {
        variant: [
          'capsule-solid-primary',
          'capsule-outline-mono',
          'capsule-outline-blue',
          'capsule-outline-purple',
          'capsule-outline-light-blue',
        ],
        size: 'lg',
        class: 'h-10 px-4 py-1.5 gap-1 text-heading-medium',
      },
      {
        variant: [
          'capsule-solid-primary',
          'capsule-outline-mono',
          'capsule-outline-blue',
          'capsule-outline-purple',
          'capsule-outline-light-blue',
        ],
        size: 'md',
        class: 'h-9 px-3 py-1.5 gap-1 text-body-small',
      },
      {
        variant: [
          'capsule-solid-primary',
          'capsule-outline-mono',
          'capsule-outline-blue',
          'capsule-outline-purple',
          'capsule-outline-light-blue',
        ],
        size: 'sm',
        class: 'h-9 px-3 py-1.5 gap-1 text-body-small',
      },
      {
        variant: [
          'capsule-solid-primary',
          'capsule-outline-mono',
          'capsule-outline-blue',
          'capsule-outline-purple',
          'capsule-outline-light-blue',
        ],
        size: 'xs',
        class: 'h-9 px-3 py-1.5 gap-1 text-body-small',
      },

      /* ── Text sizes ── */
      {
        variant: ['text-primary-blue', 'text-secondary-mono'],
        size: 'lg',
        class: 'h-10 px-3 py-1.5 gap-1.5 text-heading-medium',
      },
      {
        variant: ['text-primary-blue', 'text-secondary-mono'],
        size: 'md',
        class: 'h-8 px-1.5 py-1 gap-0.5 text-body-small',
      },
      {
        variant: ['text-primary-blue', 'text-secondary-mono'],
        size: 'sm',
        class: 'h-7 px-1 py-0.5 gap-0.5 text-body-xsmall',
      },
      {
        variant: ['text-primary-blue', 'text-secondary-mono'],
        size: 'xs',
        class: 'h-7 px-1 py-0.5 gap-0.5 text-body-xsmall',
      },

      /* ── FAB (fixed 36px) ── */
      {
        variant: ['fab-primary', 'fab-secondary'],
        size: 'lg',
        class: 'size-9 p-1.5',
      },
      {
        variant: ['fab-primary', 'fab-secondary'],
        size: 'md',
        class: 'size-9 p-1.5',
      },
      {
        variant: ['fab-primary', 'fab-secondary'],
        size: 'sm',
        class: 'size-9 p-1.5',
      },
      {
        variant: ['fab-primary', 'fab-secondary'],
        size: 'xs',
        class: 'size-9 p-1.5',
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
