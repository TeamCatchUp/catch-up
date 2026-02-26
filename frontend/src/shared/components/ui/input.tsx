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
        'text-body-small text-gray-80 placeholder:text-gray-30 flex w-full rounded-lg bg-white transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        inputSize === 'lg' && 'border-neutral-3 focus:border-blue-30 gap-3 border p-3',
        inputSize === 'sm' && 'border-neutral-5 focus:border-blue-30 gap-1 border px-2.5 py-1.5',
        error && 'border-red-50 focus:border-red-50',
        className,
      )}
      {...props}
    />
  );
}

export { Input };
