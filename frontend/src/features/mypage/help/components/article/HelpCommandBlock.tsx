'use client';

import { useState } from 'react';

import CheckIcon from '@/public/icons/icon/check.svg';
import CopyIcon from '@/public/icons/icon/copy.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

interface HelpCommandBlockProps {
  value?: string;
  ariaLabel: string;
  isLoading?: boolean;
  isError?: boolean;
}

export default function HelpCommandBlock({ value, ariaLabel, isLoading, isError }: HelpCommandBlockProps) {
  const [copied, setCopied] = useState(false);
  const canCopy = Boolean(value) && !isLoading && !isError;
  const displayValue = isLoading
    ? '명령어를 불러오는 중입니다.'
    : isError
      ? '명령어를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'
      : value;
  const hasExplicitLineBreak = displayValue?.includes('\n');

  const handleCopy = async () => {
    if (!canCopy || !value) return;

    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <section
      className={cn(
        'border-line-normal-neutral bg-fill-normal-strong flex w-full gap-4 overflow-hidden rounded-2xl border px-4 py-3',
        hasExplicitLineBreak ? 'items-start' : 'items-center',
      )}
    >
      <pre className="text-body-small text-text-normal-neutral flex min-w-0 flex-1 flex-col justify-center font-[inherit] break-words whitespace-pre-wrap">
        <code className="font-[inherit]">{displayValue}</code>
      </pre>
      <Button
        type="button"
        variant="icon-only-gray"
        size="lg"
        aria-label={ariaLabel}
        disabled={!canCopy}
        onClick={handleCopy}
        className="size-9 rounded-lg p-1.5"
      >
        {copied ? <CheckIcon className="size-6" /> : <CopyIcon className="size-6" />}
      </Button>
    </section>
  );
}
