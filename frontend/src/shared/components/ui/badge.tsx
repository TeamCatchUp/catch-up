'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/shared/utils/cn';

const badgeVariants = cva('inline-flex items-center rounded-full tracking-tight transition-colors', {
  variants: {
    variant: {
      default: 'bg-blue-5 text-blue-50',
      secondary: 'bg-fill-strong text-content-neutral',
      success: 'bg-green-5 text-green-60',
      violet: 'bg-violet-5 text-violet-60',
      orange: 'bg-orange-5 text-orange-60',
      pink: 'bg-pink-5 text-pink-60',
      red: 'bg-red-5 text-red-50',
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
