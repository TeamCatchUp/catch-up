'use client';

import Link from 'next/link';

import ChatIcon from '@/public/icons/icon/chat.svg';
import type { SearchQuery } from '@/shared/types/query/search';

interface RecentSearchListProps {
  title: string;
  querys: SearchQuery[];
}

export function RecentSearchList({ title, querys }: RecentSearchListProps) {
  if (!querys || querys.length === 0)
    return (
      <div className="flex w-full flex-col gap-2.5">
        <span className="text-body-xsmall text-content-alternative px-1.5 font-medium">{title}</span>
        <div className="flex flex-col gap-1">
          <div className="border-edge-assistive flex w-full items-center justify-center rounded-xl border border-dashed py-4">
            <span className="text-body-xsmall text-content-assistive">최근 검색기록이 없습니다.</span>
          </div>
        </div>
      </div>
    );
  return (
    <div className="flex w-full flex-col gap-2.5">
      <span className="text-body-xsmall text-content-alternative px-1.5 font-medium">{title}</span>
      <div className="flex flex-col gap-1">
        {querys.slice(0, 5).map((item, index) => (
          <Link
            href={`/chat/${item.session_id}${item.message_id != null ? `?scrollTo=${item.message_id}` : ''}`}
            key={`recent-query-${index}`}
            className="hover:bg-fill-interaction-hover group bg-fill-normal flex h-10 w-full cursor-pointer items-center gap-2 rounded-xl px-2 py-1 transition-colors"
          >
            <div className="rounded-rounded border-edge-neutral bg-fill-strong flex shrink-0 items-center justify-center gap-2.5 border p-1.5">
              <ChatIcon className="text-icon-neutral h-5 w-5" />
            </div>
            <div className="text-content-normal text-body-small flex-1 truncate text-left">{item.query}</div>
            <div className="text-body-xsmall text-content-assistive w-18 shrink-0 text-right">{item.date}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
