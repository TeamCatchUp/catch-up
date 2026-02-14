/**
 * SideNavQuestions
 * 사이드바 최근 질문 목록 + 채팅방 데이터 조회
 */

'use client';

import { useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { chatQueries } from '@/shared/queries/chatroom.queries';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

import ArrowRight from '/public/icons/icon/arrow_right.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';

interface ChatRoomQuery {
  title: string;
  session_id: string;
}

// 질문 아이템 상태별 스타일
const defaultClass = 'bg-white hover:bg-neutral-2 active:bg-neutral-3 active:ring-1 active:ring-neutral-3';
const selectedClass = 'ring-1 ring-neutral-2 bg-blue-1 hover:bg-blue-5';

export default function SideNavQuestions() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { togglePanel } = useSidebarStore();

  const { data: chatroomData } = useQuery(chatQueries.recentRooms());

  const recentChatrooms = useMemo<ChatRoomQuery[]>(() => {
    if (!chatroomData?.content) return [];
    return chatroomData.content
      .map((item) => ({
        title: item.title,
        session_id: item.session_id,
      }))
      .reverse();
  }, [chatroomData]);

  // refresh_sidebar 이벤트 → TanStack Query invalidation
  useEffect(() => {
    const handleRefresh = () => {
      queryClient.invalidateQueries({ queryKey: chatQueries.all() });
    };
    window.addEventListener('refresh_sidebar', handleRefresh);
    return () => window.removeEventListener('refresh_sidebar', handleRefresh);
  }, [queryClient]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <button onClick={() => togglePanel('questionsHistory')} className="h-7 w-fit cursor-pointer items-center">
        <div className="text-button-secondary-mono flex items-center px-2.5 py-1">
          <span className="text-body-xsmall text-gray-70">내 질문</span>
          <ArrowRight className="relative bottom-px h-5 w-5 text-gray-50" />
        </div>
      </button>
      <div className="mt-2 flex flex-col overflow-y-auto">
        {recentChatrooms.map((chatroom) => {
          const isActive = pathname === `/chat/${chatroom.session_id}`;

          return (
            <Link
              href={`/chat/${chatroom.session_id}?q=${encodeURIComponent(chatroom.title)}`}
              key={chatroom.session_id}
              className={cn('group flex cursor-pointer rounded-lg py-2', isActive ? selectedClass : defaultClass)}
            >
              <span className={cn('text-body-small truncate px-2.5')}>{chatroom.title}</span>
              <span className="mr-2.5 ml-auto flex h-5 w-5 items-center opacity-0 transition-opacity group-hover:opacity-100">
                <Kebeb className="h-4.5 w-4.5 text-gray-50" />
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
