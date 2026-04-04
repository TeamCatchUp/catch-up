'use client';

import * as React from 'react';

import { cn } from '@/shared/utils/cn';

type InputProps = React.ComponentProps<'input'> & {
  /** lg: p-3 (로그인/회원가입), sm: px-2.5 py-1.5 (필터/검색) */
  inputSize?: 'lg' | 'sm';
  error?: boolean;
};

function Input({ className, type, inputSize = 'lg', error = false, ...props }: InputProps) {
  return (
    <input
      type={type}
      className={cn(
        'text-body-small text-content-normal placeholder:text-content-assistive bg-fill-normal flex w-full rounded-lg transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        inputSize === 'lg' && 'border-edge-neutral focus:border-edge-primary gap-3 border p-3',
        inputSize === 'sm' && 'border-edge-strong focus:border-edge-primary gap-1 border px-2.5 py-1.5',
        error && 'border-status-destructive focus:border-status-destructive',
        className,
      )}
      {...props}
    />
  );
}

export { Input };
