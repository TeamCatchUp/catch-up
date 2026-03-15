'use client';

import Link from 'next/link';

import type { SearchQuery } from '@/shared/types/query/search';
import { formatRelativeDate } from '@/shared/utils/formatDate';

interface RecentlySearchProps {
  querys: (SearchQuery & { rawDate: Date })[];
  isModal?: boolean;
  onItemClick?: () => void;
}

type SearchHistoryItem = SearchQuery & { rawDate: Date };

export function SearchHistory({ querys, isModal = false, onItemClick }: RecentlySearchProps) {
  if (!querys || querys.length === 0) {
    return (
      <div className="flex w-full items-center justify-center rounded-xl py-4">
        <span className="text-body-xsmall text-content-assistive">최근 검색기록이 없습니다.</span>
      </div>
    );
  }

  const getGroupedData = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(today.getDate() - 7);
    sevenDaysAgo.setHours(0, 0, 0, 0);

    return querys.reduce(
      (acc, item) => {
        const itemDate = new Date(item.rawDate);
        itemDate.setHours(0, 0, 0, 0);

        if (itemDate.getTime() === today.getTime()) {
          acc.today.push(item);
        } else if (itemDate.getTime() >= sevenDaysAgo.getTime()) {
          acc.sevenDays.push(item);
        } else {
          acc.others.push(item);
        }
        return acc;
      },
      {
        today: [] as SearchHistoryItem[],
        sevenDays: [] as SearchHistoryItem[],
        others: [] as SearchHistoryItem[],
      },
    );
  };

  const grouped = getGroupedData();
  const sections = [
    { key: '오늘', data: grouped.today },
    { key: '최근 7일', data: grouped.sevenDays },
    { key: '이전', data: grouped.others },
  ];

  const visibleSections = sections.filter((section) => section.data.length > 0);

  return (
    <div className={`flex w-full flex-col gap-2 ${isModal ? '' : ''}`}>
      {visibleSections.map((section) => (
        <div key={section.key} className="bg-fill-normal flex flex-col gap-1 rounded-lg px-1.5 py-2.5">
          <div className="px-2">
            <span className="text-body-xsmall text-content-alternative font-medium">{section.key}</span>
          </div>

          <div className="flex flex-col gap-2">
            {section.data.map((item, index) => (
              <Link
                href={`/chat/${item.session_id}${item.message_id != null ? `?scrollTo=${item.message_id}` : ''}`}
                onClick={() => onItemClick?.()}
                key={`${item.session_id}-${index}`}
                className="hover:bg-fill-interaction-hover group bg-fill-normal flex h-10 w-full items-center gap-2 rounded-lg px-2 py-1 transition-colors"
              >
                <div className="text-content-normal text-body-small flex-1 truncate text-left">{item.query}</div>
                {section.key !== '오늘' && (
                  <div className="text-body-xsmall text-content-assistive shrink-0 text-right">
                    {section.key === '최근 7일' ? formatRelativeDate(item.rawDate.toISOString()) : item.date}
                  </div>
                )}
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
