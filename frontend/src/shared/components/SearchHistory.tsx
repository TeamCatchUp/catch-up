'use client';

import Link from 'next/link';

import Chat2 from '@/public/icons/icon/chat2.svg';
import { Separator } from '@/shared/components/ui/separator';
import type { SearchQuery } from '@/shared/types/query/search';
import { groupItemsByDate } from '@/shared/utils/dateGrouping';
import { formatRelativeTime } from '@/shared/utils/formatDate';

interface RecentlySearchProps {
  querys: (SearchQuery & { rawDate: Date })[];
  isModal?: boolean;
  onItemClick?: () => void;
}

export function SearchHistory({ querys, isModal = false, onItemClick }: RecentlySearchProps) {
  if (!querys || querys.length === 0) {
    return (
      <div className="flex w-full items-center justify-center rounded-xl py-4">
        <span className="text-body-xsmall text-content-assistive">최근 검색기록이 없습니다.</span>
      </div>
    );
  }

  const visibleSections = groupItemsByDate(querys, (item) => item.rawDate);

  return (
    <div className="flex w-full flex-col">
      {visibleSections.map((section, sectionIndex) => (
        <div key={section.key}>
          {sectionIndex > 0 && <Separator className="my-5" />}
          <div className="flex flex-col gap-1.5">
            <div className="px-3">
              <span className="text-body-xsmall text-content-neutral font-medium">{section.title}</span>
            </div>
            {section.items.map((item, index) => (
              <Link
                href={`/chat/${item.session_id}${item.message_id != null ? `?scrollTo=${item.message_id}` : ''}`}
                onClick={() => onItemClick?.()}
                key={`${item.session_id}-${index}`}
                className="hover:bg-fill-interaction-hover flex w-full items-center gap-4 rounded-lg px-3 py-2.5 transition-colors"
              >
                <Chat2 className="text-icon-normal size-5.5 shrink-0" />
                <span className="text-content-normal text-body-small flex-1 truncate text-left">{item.query}</span>
                <span className="text-body-xsmall text-content-assistive shrink-0">
                  {formatRelativeTime(item.rawDate.toISOString())}
                </span>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
