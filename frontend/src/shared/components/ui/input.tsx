'use client';

import * as React from 'react';

import { cn } from '@/shared/utils/cn';

type InputProps = React.ComponentProps<'input'> & {
  /** lg: h-[46px] p-3 (로그인/회원가입), sm: h-9 px-2.5 py-1.5 (필터/검색) */
  inputSize?: 'lg' | 'sm';
  error?: boolean;
};

function Input({ className, type, inputSize = 'lg', error = false, ...props }: InputProps) {
  return (
    <input
      type={type}
      className={cn(
        'flex w-full rounded-lg bg-white text-body-small text-gray-80 placeholder:text-gray-30 transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        inputSize === 'lg' && 'h-[46px] min-h-[46px] p-3 gap-3 border border-neutral-3 focus:border-blue-30',
        inputSize === 'sm' && 'h-9 px-2.5 py-1.5 gap-1 border border-neutral-5 focus:border-blue-30',
        error && 'border-red-50 focus:border-red-50',
        className,
      )}
      {...props}
    />
  );
}

export { Input };
