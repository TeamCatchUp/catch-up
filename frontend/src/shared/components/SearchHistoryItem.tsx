'use client';

// 검색 기록 한 줄.

import Clock from '@/public/icons/icon/clock.svg';

interface SearchHistoryItemProps {
  query: string;
  dateLabel: string;
  onClick?: () => void;
}

export default function SearchHistoryItem({ query, dateLabel, onClick }: SearchHistoryItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="hover:bg-fill-normal-interaction-hover flex h-10 w-full cursor-pointer items-center gap-2 rounded-xl px-2 py-1 text-left transition-colors"
    >
      <span className="bg-fill-normal-strong border-line-normal-neutral text-icon-normal-normal flex shrink-0 items-center justify-center rounded-full border p-1.5">
        <Clock className="h-5 w-5" />
      </span>
      <span className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate">{query}</span>
      <span className="text-body-xsmall text-text-normal-assistive whitespace-nowrap">{dateLabel}</span>
    </button>
  );
}
