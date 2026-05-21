'use client';

// 검색 기록 목록. createdAt 기준 오늘/최근 7일/이전으로 그룹화.
// 그룹화는 shared util(groupItemsByDate)을 사용하고, maxPerGroup으로 그룹별 상한 적용.

import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import { DATE_SECTION_LABELS, groupItemsByDate } from '@/shared/utils/dateGrouping';
import { formatRelativeTime } from '@/shared/utils/formatDate';

import SearchHistoryItem from './SearchHistoryItem';

interface SearchHistoryListProps {
  entries: SearchHistoryEntry[];
  isLoading?: boolean;
  maxPerGroup?: number;
  onItemClick?: (entry: SearchHistoryEntry) => void;
}

export default function SearchHistoryList({
  entries,
  isLoading = false,
  maxPerGroup,
  onItemClick,
}: SearchHistoryListProps) {
  if (isLoading && entries.length === 0) return null;

  if (!isLoading && entries.length === 0) {
    return (
      <div className="flex w-full items-center justify-center py-4">
        <span className="text-body-small text-content-assistive">최근 검색 기록이 없습니다</span>
      </div>
    );
  }

  const sections = groupItemsByDate(entries, (entry) => entry.createdAt);
  const limit = maxPerGroup ?? Infinity;

  return (
    <div className="flex w-full flex-col gap-3">
      {sections.map((section) => {
        const items = section.items.slice(0, limit);
        if (items.length === 0) return null;
        return (
          <div key={section.key} className="flex w-full flex-col gap-2.5">
            <div className="flex items-center px-2">
              <span className="text-body-xsmall text-content-alternative">{DATE_SECTION_LABELS[section.key]}</span>
            </div>
            <div className="flex w-full flex-col gap-1">
              {items.map((entry) => (
                <SearchHistoryItem
                  key={entry.id}
                  query={entry.query}
                  dateLabel={formatRelativeTime(entry.createdAt.toISOString())}
                  onClick={onItemClick ? () => onItemClick(entry) : undefined}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
