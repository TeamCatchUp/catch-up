'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import AddSmall from '@/public/icons/icon/add_small.svg';
import Cancel from '@/public/icons/icon/cancel.svg';
import Search from '@/public/icons/icon/search.svg';
import { SearchHistory } from '@/shared/components/SearchHistory';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import type { SearchQuery } from '@/shared/types/query/search';
import { formatFullDate } from '@/shared/utils/formatDate';

type SearchQueryWithRawDate = SearchQuery & { rawDate: Date };

const QuestionsHistoryPanel = () => {
  const router = useRouter();
  const { setActivePanel } = useSidebarStore();
  const [searchValue, setSearchValue] = useState('');
  const sentinelRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } = useInfiniteQuery(
    chatQueries.recentQueriesInfinite(),
  );

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

  const recentQueries = useMemo<SearchQueryWithRawDate[]>(() => {
    const items = data?.pages.flatMap((page) => page.items) ?? [];
    if (items.length === 0) return [];
    return items.map((item) => ({
      query: item.content,
      session_id: item.session_id,
      date: formatFullDate(item.created_at),
      rawDate: new Date(item.created_at),
      message_id: item.id,
    }));
  }, [data?.pages]);

  const keyword = searchValue.trim().toLowerCase();
  const filteredQueries = keyword
    ? recentQueries.filter((item) => item.query.toLowerCase().includes(keyword))
    : recentQueries;

  const handleNewQuestion = () => {
    setActivePanel(null);
    router.push('/search');
  };

  const handleClose = () => {
    setActivePanel(null);
  };

  const handleItemClick = () => {
    setActivePanel(null);
  };

  return (
    <div className="border-edge-neutral bg-fill-strong shadow-panel flex h-screen w-95 shrink-0 flex-col gap-2.5 border-r px-2 pt-4">
      {/* Header: Title + Action Buttons */}
      <div className="flex items-center justify-between px-1">
        <h2 className="text-heading-medium text-content-normal">내 질문 기록</h2>
        <div className="flex items-center gap-1.5">
          {/* 새 질문 Button */}
          <button
            onClick={handleNewQuestion}
            className="border-edge-neutral hover:bg-fill-interaction-hover bg-fill-normal flex h-7.5 cursor-pointer items-center gap-1 rounded-lg border px-2 py-1"
            aria-label="새 질문"
          >
            <AddSmall className="text-icon-neutral h-5 w-5" />
            <span className="text-body-xsmall text-content-normal">새 질문</span>
          </button>
          {/* Close Icon Button */}
          <button
            onClick={handleClose}
            className="border-edge-neutral rounded-md2 hover:bg-fill-interaction-hover bg-fill-normal flex h-7.5 w-7.5 cursor-pointer items-center justify-center border"
            aria-label="패널 닫기"
          >
            <Cancel className="text-icon-neutral h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Search Input Field */}
      <div className="px-1">
        <div className="border-edge-neutral bg-fill-normal flex h-9 items-center gap-1 rounded-lg border px-2.5 py-1.5">
          <Search className="text-icon-assistive h-5 w-5 shrink-0" />
          <input
            type="text"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            placeholder="지난 질문 검색"
            className="text-body-small text-content-normal placeholder:text-content-assistive w-full bg-transparent outline-none"
          />
        </div>
      </div>

      {/* Question List - Scrollable Area */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-1">
        {isLoading ? (
          <div className="text-content-assistive flex items-center justify-center py-8">
            데이터를 불러오는 중입니다...
          </div>
        ) : searchValue.trim() && filteredQueries.length === 0 ? (
          <div className="text-content-assistive flex items-center justify-center py-8">검색 결과가 없습니다.</div>
        ) : (
          <SearchHistory querys={filteredQueries} isModal={false} onItemClick={handleItemClick} />
        )}
        {isFetchingNextPage && (
          <div className="text-content-assistive flex items-center justify-center py-4">불러오는 중...</div>
        )}
        <div ref={sentinelRef} className="h-1" />
      </div>
    </div>
  );
};

export default QuestionsHistoryPanel;
