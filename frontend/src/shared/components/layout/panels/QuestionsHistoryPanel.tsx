'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { USE_MOCK } from '@/shared/mocks/config';
import { MOCK_RECENT_QUERIES } from '@/shared/mocks/search/data';
import { SearchHistory } from '@/shared/components/SearchHistory';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import type { SearchQuery } from '@/shared/types/query/search';
import { formatFullDate } from '@/shared/utils/formatDate';

import AddSmall from '/public/icons/icon/add_small.svg';
import Cancel from '/public/icons/icon/cancel.svg';
import Search from '/public/icons/icon/search.svg';

type SearchQueryWithRawDate = SearchQuery & { rawDate: Date };

const QuestionsHistoryPanel = () => {
  const router = useRouter();
  const { setActivePanel } = useSidebarStore();
  const [searchValue, setSearchValue] = useState('');

  const { data, isLoading } = useQuery(chatQueries.recentQueries());

  const recentQueries = useMemo<SearchQueryWithRawDate[]>(() => {
    // Mock 데이터 사용 모드 (NEXT_PUBLIC_USE_MOCK=true)
    if (USE_MOCK) {
      return MOCK_RECENT_QUERIES.items.map((item) => ({
        query: item.content,
        session_id: item.session_id,
        date: formatFullDate(item.created_at),
        rawDate: new Date(item.created_at),
      }));
    }

    // 실제 API 데이터 사용
    if (!data?.items) return [];
    return data.items.map((item) => ({
      query: item.content,
      session_id: item.session_id,
      date: formatFullDate(item.created_at),
      rawDate: new Date(item.created_at),
    }));
  }, [data]);

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
    <div className="border-neutral-3 bg-neutral-1 shadow-panel flex h-screen w-95 shrink-0 flex-col gap-2.5 border-r px-2 pt-4">
      {/* Header: Title + Action Buttons */}
      <div className="flex items-center justify-between px-1">
        <h2 className="text-heading-medium text-gray-80">내 질문 기록</h2>
        <div className="flex items-center gap-1.5">
          {/* 새 질문 Button - Box button with icon + text per Figma */}
          <button
            onClick={handleNewQuestion}
            className="border-neutral-3 hover:bg-neutral-2 flex h-7.5 cursor-pointer items-center gap-1 rounded-lg border bg-white px-2 py-1"
            aria-label="새 질문"
          >
            <AddSmall className="h-5 w-5 text-gray-50" />
            <span className="text-body-xsmall text-gray-80">새 질문</span>
          </button>
          {/* Close Icon Button */}
          <button
            onClick={handleClose}
            className="border-neutral-3 rounded-md2 hover:bg-neutral-2 flex h-7.5 w-7.5 cursor-pointer items-center justify-center border bg-white"
            aria-label="패널 닫기"
          >
            <Cancel className="h-5 w-5 text-gray-50" />
          </button>
        </div>
      </div>

      {/* Search Input Field */}
      <div className="px-1">
        <div className="border-neutral-3 flex h-9 items-center gap-1 rounded-lg border bg-white px-2.5 py-1.5">
          <Search className="text-gray-40 h-5 w-5 shrink-0" />
          <input
            type="text"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            placeholder="지난 질문 검색"
            className="text-body-small text-gray-80 placeholder:text-gray-30 w-full bg-transparent outline-none"
          />
        </div>
      </div>

      {/* Question List - Scrollable Area */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-1">
        {!USE_MOCK && isLoading ? (
          <div className="text-gray-30 flex items-center justify-center py-8">데이터를 불러오는 중입니다...</div>
        ) : (
          <SearchHistory querys={recentQueries} isModal={false} onItemClick={handleItemClick} />
        )}
      </div>
    </div>
  );
};

export default QuestionsHistoryPanel;
