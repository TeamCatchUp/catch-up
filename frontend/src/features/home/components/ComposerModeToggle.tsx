'use client';

// 컴포저 안에 들어가는 [캐치스턴트 AI | 문서 탐색] 세그먼트 토글.
// 시안에 hover/pressed가 없어 선택/비선택 두 상태만 둔다.

import { cn } from '@/shared/utils/cn';

import type { HomeMode } from './ModePicker';

const OPTIONS: ReadonlyArray<{ value: HomeMode; label: string }> = [
  { value: 'ai', label: '캐치스턴트 AI' },
  { value: 'docs', label: '문서 탐색' },
];

interface ComposerModeToggleProps {
  mode: HomeMode;
  onModeChange: (next: HomeMode) => void;
  className?: string;
}

export default function ComposerModeToggle({ mode, onModeChange, className }: ComposerModeToggleProps) {
  return (
    <div
      role="tablist"
      aria-label="모드 선택"
      className={cn(
        'border-line-normal-neutral bg-fill-normal-strong flex items-center gap-0.5 rounded-lg border border-solid p-0.5',
        className,
      )}
    >
      {OPTIONS.map((opt) => {
        const isActive = opt.value === mode;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onModeChange(opt.value)}
            className={cn(
              'text-body-small flex h-8 cursor-pointer items-center justify-center rounded-lg border border-solid px-2.5 whitespace-nowrap',
              isActive
                ? 'bg-fill-normal-normal border-line-normal-assistive text-text-normal-normal'
                : 'text-text-normal-alternative border-transparent',
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
