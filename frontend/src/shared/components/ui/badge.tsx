'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

const badgeVariants = cva('inline-flex items-center whitespace-nowrap rounded-full transition-colors', {
  variants: {
    variant: {
      default: 'bg-fill-primary-normal-neutral text-content-primary',
      secondary: 'bg-fill-interaction-hover text-content-alternative',
      success: 'bg-accent-green-neutral text-accent-green',
      violet: 'bg-accent-violet-neutral text-accent-violet',
      orange: 'bg-accent-red-orange-neutral text-accent-red-orange',
      pink: 'bg-accent-pink-lighten text-accent-pink',
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
