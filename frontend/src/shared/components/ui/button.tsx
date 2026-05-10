'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

const buttonVariants = cva(
  'inline-flex shrink-0 cursor-pointer items-center justify-center transition-colors focus-visible:outline-none disabled:pointer-events-none',
  {
    variants: {
      variant: {
        /* ── Icon Buttons ── */
        'icon-solid-blue':
          'hover:bg-fill-primary-interaction-hover active:bg-fill-primary-interaction-pressed disabled:bg-fill-primary-interaction-inactive bg-fill-primary rounded-lg text-white',
        'icon-outline-gray':
          'border-edge-neutral hover:border-edge-normal hover:bg-fill-interaction-hover active:border-edge-strong active:bg-fill-interaction-pressed disabled:border-edge-assistive disabled:text-content-assistive text-icon-normal bg-fill-normal rounded-lg border',
        'icon-only-gray':
          'hover:text-icon-normal hover:bg-fill-interaction-hover active:text-icon-normal active:bg-fill-interaction-pressed disabled:text-content-assistive text-icon-neutral rounded-lg',
        'icon-only-blue':
          'hover:bg-fill-primary-interaction-hover-assistive active:bg-fill-primary-interaction-hover-assistive active:text-icon-primary-strong disabled:text-content-assistive text-icon-primary rounded-full',

        /* ── Box Buttons ── */
        'box-solid-primary':
          'hover:bg-fill-primary-interaction-hover active:bg-fill-primary-interaction-pressed disabled:bg-fill-interaction-inactive disabled:text-content-assistive disabled:[&_svg]:text-icon-assistive bg-fill-primary rounded-lg text-white',
        'box-outline-gray':
          'border-edge-neutral hover:border-edge-normal hover:bg-fill-interaction-hover active:border-edge-strong active:bg-fill-interaction-pressed disabled:bg-fill-interaction-inactive disabled:border-edge-normal disabled:text-content-assistive disabled:[&_svg]:text-icon-assistive text-icon-normal bg-fill-normal rounded-lg border',
        'box-outline-blue':
          'border-edge-primary hover:bg-fill-primary-interaction-hover-assistive active:bg-fill-primary-interaction-hover-assistive disabled:bg-fill-interaction-inactive disabled:text-content-assistive disabled:border-edge-normal disabled:[&_svg]:text-icon-assistive bg-fill-primary-assistive text-content-primary rounded-lg border',
        'box-soft-primary':
          'bg-fill-primary-normal-neutral border-edge-neutral text-content-primary hover:bg-fill-primary-interaction-hover-assistive active:bg-fill-primary-interaction-hover-assistive disabled:bg-fill-interaction-inactive disabled:border-edge-normal disabled:text-content-assistive disabled:[&_svg]:text-icon-assistive rounded-lg border',

        /* ── Capsule Buttons ── */
        'capsule-solid-primary':
          'hover:bg-fill-primary-interaction-hover active:bg-fill-primary-interaction-pressed disabled:bg-fill-interaction-inactive disabled:text-content-assistive disabled:[&_svg]:text-icon-assistive bg-fill-primary rounded-full text-white',
        'capsule-outline-mono':
          'border-edge-normal hover:bg-fill-interaction-hover active:border-edge-neutral active:bg-fill-interaction-pressed disabled:border-edge-normal disabled:bg-fill-interaction-inactive disabled:text-content-assistive disabled:[&_svg]:text-icon-assistive bg-fill-normal rounded-full border',
        'capsule-outline-blue':
          'border-edge-primary bg-fill-primary-assistive text-content-primary hover:bg-fill-primary-interaction-hover-assistive active:bg-fill-primary-interaction-hover-assistive active:border-edge-primary-strong disabled:text-content-assistive disabled:bg-fill-interaction-inactive disabled:border-edge-normal disabled:[&_svg]:text-icon-assistive rounded-full border',
        'capsule-solid-purple': 'bg-accent-violet-neutral rounded-full',
        'capsule-solid-light-blue': 'bg-accent-light-blue-lighten rounded-full',

        /* ── Text Buttons ── */
        'text-primary-blue':
          'hover:bg-fill-primary-interaction-hover-assistive active:bg-fill-primary-interaction-hover-assistive text-content-primary rounded-full',
        'text-secondary-mono':
          'hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed disabled:text-content-assistive text-icon-normal rounded-full',

        /* ── FAB ── */
        'fab-primary':
          'bg-accent-black-lighten hover:bg-accent-black active:bg-accent-black shadow-button text-icon-inverse rounded-full',
        'fab-secondary':
          'hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed text-icon-normal shadow-button border-edge-neutral bg-fill-normal rounded-full border',
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
