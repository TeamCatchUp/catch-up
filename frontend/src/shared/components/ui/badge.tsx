'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

const badgeVariants = cva('inline-flex items-center rounded-full whitespace-nowrap transition-colors', {
  variants: {
    variant: {
      default: 'bg-fill-primary-normal-neutral text-text-primary-normal',
      secondary: 'bg-fill-normal-interaction-hover text-text-normal-alternative',
      success: 'bg-accent-green-neutral text-accent-green-default',
      violet: 'bg-accent-violet-neutral text-accent-violet-default',
      orange: 'bg-accent-red-orange-neutral text-accent-red-orange-default',
      pink: 'bg-accent-pink-lighten text-accent-pink-default',
      red: 'bg-accent-red-lighten text-status-destructive',
    },
    size: {
      md: 'text-body-xsmall px-3 py-1.5',
      sm: 'text-label-xsmall px-1.5 py-1.5',
    },
  },
  defaultVariants: {
    variant: 'default',
    size: 'md',
  },
});

type BadgeProps = React.ComponentProps<'span'> & VariantProps<typeof badgeVariants>;

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, size, className }))} {...props} />;
}

export { Badge, badgeVariants };
