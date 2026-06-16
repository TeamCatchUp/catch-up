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
        'text-body-small text-text-normal-normal placeholder:text-text-normal-assistive bg-fill-normal-normal flex w-full rounded-lg transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        inputSize === 'lg' &&
          'border-line-normal-neutral focus:border-line-primary-normal gap-3 border p-3 focus:border-[1.5px]',
        inputSize === 'sm' &&
          'border-line-normal-strong focus:border-line-primary-normal gap-1 border px-2.5 py-1.5 focus:border-[1.5px]',
        error && 'border-status-destructive focus:border-status-destructive border-[1.5px] focus:border-[1.5px]',
        className,
      )}
      {...props}
    />
  );
}

export { Input };
