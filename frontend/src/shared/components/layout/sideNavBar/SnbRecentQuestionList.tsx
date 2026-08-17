'use client';

import { useEffect, useMemo, useRef } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { usePathname } from 'next/navigation';

import { chatQueries } from '@/shared/queries/chatroom.queries';

import SnbChatTitleRow from './SnbChatTitleRow';

/**
 * 홈 SNB의 최근 질문 목록. 조회·무한스크롤·갱신 이벤트는 구 사이드바 계약 그대로다.
 * 빈 목록 문구는 만들지 않는다 — 승인된 카피가 없다.
 */
export default function SnbRecentQuestionList() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const sentinelRef = useRef<HTMLDivElement>(null);

  const { data, hasNextPage, isFetchingNextPage, fetchNextPage } = useInfiniteQuery(chatQueries.recentRoomsInfinite());

  const chatrooms = useMemo(() => data?.pages.flatMap((page) => page.items) ?? [], [data?.pages]);

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
    <div className="flex min-w-0 flex-col">
      {chatrooms.map((chatroom) => (
        <SnbChatTitleRow
          key={chatroom.session_id}
          label={chatroom.title}
          href={`/chat/${chatroom.session_id}`}
          selected={pathname === `/chat/${chatroom.session_id}`}
        />
      ))}
      {isFetchingNextPage && (
        <div className="text-body-xsmall text-text-normal-assistive py-2 text-center">불러오는 중...</div>
      )}
      <div ref={sentinelRef} className="h-1 shrink-0" />
    </div>
  );
}
