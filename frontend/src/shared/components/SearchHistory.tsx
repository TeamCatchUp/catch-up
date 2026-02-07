'use client';

import ChatIcon from '@/public/icons/icon/chat.svg';
import Link from 'next/link';
import type { SearchQuery } from '@/features/search/types/search';

interface RecentlySearchProps {
  querys: (SearchQuery & { rawDate: Date })[];
  isModal?: boolean;
  onItemClick?: () => void;
}

export function SearchHistory({ querys, isModal = false, onItemClick }: RecentlySearchProps) {
  if (!querys || querys.length === 0) {
    return (
      <div className="flex w-full items-center justify-center rounded-xl py-4">
        <span className="text-body-xsmall text-gray-30">최근 검색기록이 없습니다.</span>
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
      { today: [] as SearchQuery[], sevenDays: [] as SearchQuery[], others: [] as SearchQuery[] },
    );
  };

  const grouped = getGroupedData();
  const sections = [
    { key: '오늘', data: grouped.today },
    { key: '최근 7일', data: grouped.sevenDays },
    { key: '이전', data: grouped.others },
  ];

  const visibleSections = sections.filter((s) => s.data.length > 0);

  return (
    <div className="flex w-full flex-col">
      {visibleSections.map((section, idx) => (
        <div key={section.key}>
          <span className="text-body-xsmall block px-1.5 py-2 font-medium text-gray-50">{section.key}</span>

          <div className="flex flex-col gap-1">
            {section.data.map((item, i) => (
              <Link
                href={`/ragAnswer/${item.sessionId}`}
                onClick={() => onItemClick?.()}
                key={item.sessionId + i}
                className="hover:bg-neutral-2 group flex h-10 w-full items-center gap-2 rounded-xl bg-white px-2 py-1 transition-colors"
              >
                <div className="border-neutral-3 bg-neutral-1 rounded-rounded flex shrink-0 items-center justify-center border p-1.5">
                  <ChatIcon className="text-gray-60 h-4 w-4" />
                </div>
                <div className="text-gray-80 text-body-small flex-1 truncate text-left">{item.query}</div>
                <div className="text-body-xsmall text-gray-30 w-18 shrink-0 text-right">{item.date}</div>
              </Link>
            ))}
          </div>
          {!isModal && idx < visibleSections.length - 1 && <hr className="border-neutral-4 my-6 w-full border-t" />}
        </div>
      ))}
    </div>
  );
}
