'use client';

// 결과 페이지 상단 검색바.
// isFocused 상태에 따라 collapsed(rounded-full) / expanded(카드 안에 chips + 검색 기록 + promo) 두 시각.
// Figma 13426:54489(collapsed), 13426:52872(expanded) — 둘 다 w-225(900px) 고정.
// 외부 placeholder가 collapsed 높이(h-14)만큼 자리 보존, 실제 바는 absolute로 오버레이 → expanded 시 하단 콘텐츠 안 밀림.
// 내부 확장 콘텐츠는 ResultSearchBarExpandedPanel로 분리.

import { useRef, useState } from 'react';

import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconCancel from '@/public/icons/icon/cancel.svg';
import IconSearch from '@/public/icons/icon/search_2.svg';
import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';

import ResultSearchBarExpandedPanel from './ResultSearchBarExpandedPanel';

interface ResultSearchBarProps {
  value: string;
  onValueChange: (value: string) => void;
  chips: DocsSource[];
  onChipsChange: (next: DocsSource[]) => void;
  onSubmit: () => void;
  onClear: () => void;
  // true면 isFocused state 무시하고 항상 expanded. dev preview/Storybook 용도.
  forceExpanded?: boolean;
}

export default function ResultSearchBar({
  value,
  onValueChange,
  chips,
  onChipsChange,
  onSubmit,
  onClear,
  forceExpanded = false,
}: ResultSearchBarProps) {
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasText = value.trim().length > 0;
  const expanded = forceExpanded || isFocused;

  // submit 후 input blur → onBlur로 setIsFocused(false) → 패널 collapse.
  const handleSubmit = () => {
    onSubmit();
    inputRef.current?.blur();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="relative h-14 w-225">
      <div
        className={cn(
          'bg-fill-normal border-edge-normal absolute top-0 left-0 flex w-225 flex-col border',
          expanded
            ? 'shadow-strong z-dropdown gap-2.5 rounded-[28px] pt-2 pr-2 pb-4 pl-3'
            : 'items-center gap-2 rounded-full p-2',
        )}
      >
      <div className={cn('flex w-full', expanded ? 'flex-col gap-2' : 'items-center gap-2')}>
        <div className={cn('flex w-full items-center', expanded ? 'gap-3 pl-0.5' : 'gap-2')}>
          <div className={cn('flex min-w-0 flex-1 items-center', expanded ? 'gap-3.5' : 'gap-2')}>
            {expanded ? (
              <IconSearch className="text-icon-alternative h-7 w-7 shrink-0" />
            ) : (
              <div className="text-icon-alternative flex h-10 w-10 shrink-0 items-center justify-center">
                <IconSearch className="h-7 w-7" />
              </div>
            )}
            <input
              ref={inputRef}
              autoFocus={expanded && !forceExpanded}
              type="text"
              value={value}
              onChange={(e) => onValueChange(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onKeyDown={handleKeyDown}
              className="text-body-medium text-content-normal placeholder:text-content-assistive min-w-0 flex-1 bg-transparent outline-none"
              placeholder="업무, 채널 또는 문서를 검색해보세요"
            />
          </div>
          <div className="flex shrink-0 items-center gap-2.5">
            <button
              type="button"
              onMouseDown={(e) => expanded && e.preventDefault()}
              onClick={onClear}
              aria-label="검색어 지우기"
              aria-hidden={!hasText}
              tabIndex={hasText ? 0 : -1}
              className={cn(
                'text-icon-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors',
                hasText ? '' : 'pointer-events-none invisible',
              )}
            >
              <IconCancel className="h-7 w-7" />
            </button>
            <span aria-hidden className={cn('bg-edge-normal h-6 w-px shrink-0', hasText ? '' : 'invisible')} />
            <button
              type="button"
              onMouseDown={(e) => expanded && e.preventDefault()}
              onClick={handleSubmit}
              aria-label="검색"
              className={cn(
                'flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors',
                expanded
                  ? hasText
                    ? 'bg-fill-primary'
                    : 'bg-fill-interaction-inactive border-edge-assistive border'
                  : 'text-icon-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed',
              )}
            >
              <IconArrowSend
                className={cn(
                  'h-6 w-6',
                  expanded ? (hasText ? 'brightness-0 invert' : 'text-content-assistive') : 'h-7 w-7',
                )}
              />
            </button>
          </div>
        </div>
        {expanded && <span aria-hidden className="bg-edge-neutral h-px w-full" />}
      </div>
      {expanded && (
        <ResultSearchBarExpandedPanel
          selectedSources={chips}
          onSourcesToggle={onChipsChange}
        />
      )}
      </div>
    </div>
  );
}
