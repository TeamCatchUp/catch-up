'use client';

import { useState } from 'react';

import { cn } from '@/shared/utils/cn';

interface AgentInstructionFieldProps {
  value: string;
  onChange: (value: string) => void;
  maxLength: number;
  hintText: string;
}

export default function AgentInstructionField({ value, onChange, maxLength, hintText }: AgentInstructionFieldProps) {
  const [isFocused, setIsFocused] = useState(false);
  const hasValue = value.length > 0;
  const isError = value.length >= maxLength;
  const isActive = isFocused || hasValue;
  const borderColor = isError
    ? 'var(--status-destructive)'
    : isActive
      ? 'var(--line-primary-normal)'
      : 'var(--line-neutral)';
  const borderWidth = isError || isActive ? 1.5 : 1;

  return (
    <label className="flex w-full flex-col gap-3">
      <span className="text-heading-small text-text-normal-normal flex items-start gap-1">
        답변 초안, 어떤 규칙으로 쓸까요?
        <span className="text-status-destructive" aria-hidden="true">
          *
        </span>
      </span>
      <div
        className="bg-fill-normal-normal flex min-h-24.5 w-full items-center rounded-xl border border-solid p-4 transition-colors"
        style={{ borderColor, borderWidth }}
      >
        <div
          className={cn(
            'flex min-w-0 flex-1 flex-col items-center justify-end px-0.5',
            hasValue ? 'gap-2.5 overflow-hidden' : 'gap-4',
          )}
        >
          <textarea
            aria-label="답변 초안, 어떤 규칙으로 쓸까요?"
            aria-invalid={isError}
            className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive [field-sizing:content] max-h-50 min-h-5.75 w-full resize-none overflow-y-auto bg-transparent p-0 leading-[1.5] outline-none"
            maxLength={maxLength}
            placeholder={hintText}
            rows={1}
            value={value}
            onBlur={() => setIsFocused(false)}
            onChange={(event) => onChange(event.target.value)}
            onFocus={() => setIsFocused(true)}
          />
          <span
            className={cn(
              'text-body-small h-5.75 w-full overflow-hidden text-ellipsis whitespace-nowrap',
              isError ? 'text-status-destructive' : 'text-text-normal-alternative',
            )}
          >
            {value.length}/{maxLength}
          </span>
        </div>
      </div>
    </label>
  );
}
