'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import AddSquare from '@/public/icons/icon/add_square.svg';
import Cancel from '@/public/icons/icon/cancel.svg';
import Search from '@/public/icons/icon/search.svg';
import { SearchHistory } from '@/shared/components/SearchHistory';
import { Button } from '@/shared/components/ui/button';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import type { SearchQuery } from '@/shared/types/query/search';
import { formatFullDate } from '@/shared/utils/formatDate';

type SearchQueryWithRawDate = SearchQuery & { rawDate: Date };

export default function QuestionsHistoryPanel() {
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
    <div className="border-edge-neutral bg-fill-strong shadow-panel flex h-screen w-95 shrink-0 flex-col gap-3 border-r px-3 pt-4">
      {/* 헤더: 타이틀 + 검색바 */}
      <div className="flex flex-col gap-2 px-2">
        <div className="flex items-center gap-1.5 pl-1">
          <h2 className="text-heading-medium text-content-strong flex-1">내 질문 기록</h2>
          <Button variant="icon-only-gray" size="md" onClick={handleClose} aria-label="패널 닫기">
            <Cancel className="text-icon-neutral h-6 w-6" />
          </Button>
        </div>
        <div className="border-edge-neutral bg-fill-normal flex h-9 items-center gap-2 rounded-lg border px-2.5 py-1.5">
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

      {/* 새 질문하기 */}
      <button
        onClick={handleNewQuestion}
        className="hover:bg-fill-interaction-hover flex cursor-pointer items-center gap-4 rounded-lg px-3 py-2.5 transition-colors"
      >
        <AddSquare className="text-icon-normal size-5.5 shrink-0" />
        <span className="text-body-small text-content-normal">새 질문하기</span>
      </button>

      {/* 질문 리스트 */}
      <div className="custom-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto">
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
}
