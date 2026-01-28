'use client';

import ChatIcon from '@/public/icons/icon/chat.svg';
import Link from 'next/link';

interface SearchQuery {
  query: string;
  sessionId: string;
  date: string;
}

interface RecentlySearchProps {
  title: string;
  querys: SearchQuery[];
}

export function ReacentlySearchList({ title, querys }: RecentlySearchProps) {
  const displayedQuerys = querys.slice(0, 3);
  if (!displayedQuerys || displayedQuerys.length === 0) return null;
  return (
    <div className="flex w-full flex-col gap-2.5">
      <span className="text-body-xsmall px-1.5 font-medium text-gray-50">{title}</span>
      <div className="flex flex-col gap-1">
        {displayedQuerys.map((item, index) => (
          <Link
            href={`/ragAnswer/${item.sessionId}`}
            key={`recent-query-${index}`}
            className="hover:bg-neutral-2 group flex h-10 w-full cursor-pointer items-center gap-2 rounded-xl bg-white px-2 py-1 transition-colors"
          >
            <div className="rounded-rounded border-neutral-3 bg-neutral-1 flex shrink-0 items-center justify-center gap-2.5 border p-1.5">
              <ChatIcon className="text-gray-60 h-4 w-4" />
            </div>
            <div className="text-gray-80 text-body-small flex-1 truncate text-left">{item.query}</div>
            <div className="text-body-xsmall text-gray-30 w-18 shrink-0 text-right">{item.date}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
