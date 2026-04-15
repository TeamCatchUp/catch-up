/**
 * SideNavQuestions
 * 사이드바 최근 질문 목록 + 채팅방 데이터 조회
 */

'use client';

import { useEffect, useMemo, useRef } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import ArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import Kebeb from '@/public/icons/icon/kebeb 2.svg';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

interface ChatRoomQuery {
  title: string;
  session_id: string;
}

// 질문 아이템 상태별 스타일
const defaultClass =
  'border border-transparent hover:bg-fill-interaction-hover hover:border-edge-assistive active:bg-fill-interaction-pressed active:border-edge-neutral';
const selectedClass = 'bg-fill-primary-normal-neutral hover:bg-fill-primary-interaction-hover-assistive';

export default function SideNavQuestions() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { togglePanel } = useSidebarStore();
  const sentinelRef = useRef<HTMLDivElement>(null);

  const { data, hasNextPage, isFetchingNextPage, fetchNextPage } = useInfiniteQuery(chatQueries.recentRoomsInfinite());

  const recentChatrooms = useMemo<ChatRoomQuery[]>(() => {
    const items = data?.pages.flatMap((page) => page.items) ?? [];
    if (items.length === 0) return [];
    return items.map((item) => ({
      title: item.title,
      session_id: item.session_id,
    }));
  }, [data?.pages]);

  // refresh_sidebar 이벤트 → TanStack Query invalidation
  useEffect(() => {
    const handleRefresh = () => {
      queryClient.invalidateQueries({ queryKey: chatQueries.all() });
    };
    window.addEventListener('refresh_sidebar', handleRefresh);
    return () => window.removeEventListener('refresh_sidebar', handleRefresh);
  }, [queryClient]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-0.5">
      <button
        onClick={() => togglePanel('questionsHistory')}
        className="hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed flex h-10 w-full cursor-pointer items-center gap-0.5 rounded-lg px-2.5 py-2"
      >
        <span className="text-label-small text-content-normal">내 질문</span>
        <ArrowRight2 className="text-icon-neutral relative -top-[0.5px] size-6 shrink-0" />
      </button>
      <div className="custom-scrollbar relative flex flex-1 overflow-y-auto">
        <div className="flex flex-1 flex-col">
          {recentChatrooms.map((chatroom) => {
            const isActive = pathname === `/chat/${chatroom.session_id}`;

            return (
              <Link
                href={`/chat/${chatroom.session_id}`}
                key={chatroom.session_id}
                className={cn(
                  'group flex h-10 cursor-pointer items-center rounded-lg px-2.5 py-2',
                  isActive ? selectedClass : defaultClass,
                )}
              >
                <span className="text-body-small flex-1 truncate">{chatroom.title}</span>
                <span className="ml-auto flex size-5 items-center opacity-0 transition-opacity group-hover:opacity-100">
                  <Kebeb className="text-icon-neutral h-4.5 w-4.5" />
                </span>
              </Link>
            );
          })}
          {isFetchingNextPage && (
            <div className="text-body-xsmall text-content-assistive py-2 text-center">불러오는 중...</div>
          )}
          <div ref={sentinelRef} className="h-1" />
          <div className="to-fill-normal pointer-events-none sticky bottom-0 z-base h-12.5 w-full shrink-0 bg-linear-to-b from-transparent" />
        </div>
      </div>
    </div>
  );
}
