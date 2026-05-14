'use client';

// 결과 페이지 상단 검색바.
// isFocused 상태에 따라 collapsed(rounded-full) / expanded(카드 안에 chips + 검색 기록 + promo) 두 시각.
// Figma 13426:54489(collapsed), 13426:52872(expanded) — 둘 다 w-225(900px) 고정.
// expanded 시 z-dropdown으로 화면 위에 떠 있고, 내부 확장 콘텐츠는 QueryBox와 동일한 fade+slide-down 애니메이션.

import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconCancel from '@/public/icons/icon/cancel.svg';
import IconSearch from '@/public/icons/icon/search_2.svg';
import SearchHistoryList from '@/shared/components/SearchHistoryList';
import SourceChipsRow from '@/shared/components/SourceChipsRow';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';
import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';

import CatchupPromoCard from './CatchupPromoCard';

interface ResultSearchBarProps {
  value: string;
  onValueChange: (value: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  // true면 isFocused state 무시하고 항상 expanded. dev preview/Storybook 용도.
  forceExpanded?: boolean;
}

export default function ResultSearchBar({
  value,
  onValueChange,
  onSubmit,
  onClear,
  forceExpanded = false,
}: ResultSearchBarProps) {
  const router = useRouter();
  const { entries: history, isLoading: isHistoryLoading } = useSearchHistoryEntries();
  const [isFocused, setIsFocused] = useState(false);
  // expanded 시각 안 chips는 결과 페이지와 별개 의미 — 자체 state 유지.
  const [chipsSources, setChipsSources] = useState<DocsSource[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasText = value.trim().length > 0;
  const expanded = forceExpanded || isFocused;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div
      className={cn(
        'bg-fill-normal border-edge-normal relative flex w-225 flex-col border',
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
              onClick={onSubmit}
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
                  expanded
                    ? hasText
                      ? 'brightness-0 invert'
                      : 'text-content-assistive'
                    : 'h-7 w-7',
                )}
              />
            </button>
          </div>
        </div>
        {expanded && <span aria-hidden className="bg-edge-neutral h-px w-full" />}
      </div>
      {expanded && (
        <div className="animate-in fade-in-0 slide-in-from-top-3 flex w-full flex-col gap-2.5 duration-300">
          <SourceChipsRow
            className="w-full justify-start"
            selectedSources={chipsSources}
            onToggle={setChipsSources}
          />
          <div className="flex w-full flex-1 items-start gap-6">
            <div className="min-w-0 flex-1">
              <SearchHistoryList
                entries={history}
                isLoading={isHistoryLoading}
                maxPerGroup={3}
                onItemClick={(entry) => router.push(`/hybrid-search?q=${encodeURIComponent(entry.query)}`)}
              />
            </div>
            <div className="w-80 shrink-0">
              <CatchupPromoCard />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
