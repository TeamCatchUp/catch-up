'use client';

// 결과 페이지 상단 검색바.
// isFocused 상태에 따라 collapsed(rounded-full) / expanded(카드 안에 chips + 검색 기록 + promo) 두 시각.

import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconCancel from '@/public/icons/icon/cancel.svg';
import IconSearch from '@/public/icons/icon/search_2.svg';
import SearchHistoryList from '@/shared/components/SearchHistoryList';
import SourceChipsRow from '@/shared/components/SourceChipsRow';
import { useSearchHistoryEntries } from '@/shared/hooks/useSearchHistoryEntries';

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
  const inputRef = useRef<HTMLInputElement>(null);
  const hasText = value.trim().length > 0;
  const expanded = forceExpanded || isFocused;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onSubmit();
    }
  };

  if (!expanded) {
    return (
      <div className="bg-fill-normal border-edge-normal flex w-full items-center gap-2 rounded-full border p-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <div className="text-icon-alternative flex h-10 w-10 shrink-0 items-center justify-center">
            <IconSearch className="h-7 w-7" />
          </div>
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => onValueChange(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onKeyDown={handleKeyDown}
            className="text-body-medium text-content-normal placeholder:text-content-assistive min-w-0 flex-1 bg-transparent outline-none"
            placeholder="업무, 채널 또는 문서를 검색해보세요"
          />
        </div>
        <div className="flex shrink-0 items-center gap-2.5">
          <button
            type="button"
            onClick={onClear}
            aria-label="검색어 지우기"
            aria-hidden={!hasText}
            tabIndex={hasText ? 0 : -1}
            className={`text-icon-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors ${
              hasText ? '' : 'pointer-events-none invisible'
            }`}
          >
            <IconCancel className="h-7 w-7" />
          </button>
          <span aria-hidden className={`bg-edge-normal h-6 w-px shrink-0 ${hasText ? '' : 'invisible'}`} />
          <button
            type="button"
            onClick={onSubmit}
            aria-label="검색"
            className="text-icon-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors"
          >
            <IconArrowSend className="h-7 w-7" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-fill-normal border-edge-normal shadow-strong flex w-full flex-col gap-2.5 rounded-[28px] border pt-2 pr-2 pb-4 pl-3">
      <div className="flex w-full flex-col gap-2">
        <div className="flex w-full items-center gap-3 pl-0.5">
          <div className="flex min-w-0 flex-1 items-center gap-3.5">
            <IconSearch className="text-icon-alternative h-7 w-7 shrink-0" />
            <input
              ref={inputRef}
              autoFocus={!forceExpanded}
              type="text"
              value={value}
              onChange={(e) => onValueChange(e.target.value)}
              onBlur={() => setIsFocused(false)}
              onKeyDown={handleKeyDown}
              className="text-body-medium text-content-normal placeholder:text-content-assistive min-w-0 flex-1 bg-transparent outline-none"
              placeholder="업무, 채널 또는 문서를 검색해보세요"
            />
          </div>
          <div className="flex shrink-0 items-center gap-2.5">
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={onClear}
              aria-label="검색어 지우기"
              aria-hidden={!hasText}
              tabIndex={hasText ? 0 : -1}
              className={`text-icon-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors ${
                hasText ? '' : 'pointer-events-none invisible'
              }`}
            >
              <IconCancel className="h-7 w-7" />
            </button>
            <span aria-hidden className={`bg-edge-normal h-6 w-px shrink-0 ${hasText ? '' : 'invisible'}`} />
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={onSubmit}
              aria-label="검색"
              className={`flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors ${
                hasText
                  ? 'bg-fill-primary'
                  : 'bg-fill-interaction-inactive border-edge-assistive border'
              }`}
            >
              <IconArrowSend className={`h-6 w-6 ${hasText ? 'brightness-0 invert' : 'text-content-assistive'}`} />
            </button>
          </div>
        </div>
        <span aria-hidden className="bg-edge-neutral h-px w-full" />
      </div>
      <SourceChipsRow className="w-full justify-start" />
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
  );
}
