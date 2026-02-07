'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import AI from '/public/icons/icon/ai.svg';
import Add from '/public/icons/icon/add_small.svg';
import Search from '/public/icons/icon/search.svg';
import Close from '/public/icons/icon/cancel.svg';
import Chat from '/public/icons/icon/chat.svg';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { SearchHistory } from '@/shared/components/SearchHistory';
import { searchService } from '@/shared/api/search';
import { formatFullDate } from '@/shared/utils/formatDate';
import type { SearchQuery } from '@/shared/types/query/search';

interface RecentQuestionsModalProps {
  onClose: () => void;
}

type SearchQueryWithRawDate = SearchQuery & { rawDate: Date };

const RecentQuestionsModal = ({ onClose }: RecentQuestionsModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const [recentQueries, setRecentQueries] = useState<SearchQueryWithRawDate[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchDefaultData = async () => {
      try {
        setIsLoading(true);

        const [queriesRes] = await Promise.all([searchService.getRecentQueries()]);

        if (queriesRes.content) {
          const mappedQueries: SearchQueryWithRawDate[] = queriesRes.content.map((item) => ({
            query: item.query,
            sessionId: item.sessionId,
            date: formatFullDate(item.createdAt),
            rawDate: new Date(item.createdAt),
          }));
          setRecentQueries(mappedQueries);
        }
      } catch (err) {
        console.error('데이터 로드 실패:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDefaultData();
  }, []);

  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  const handleNewQuestion = () => {
    onClose();
    router.push('/search');
  };

  return (
    <div
      ref={modalRef}
      className="shadow-modal border-neutral-4 flex max-h-135 w-190 flex-col gap-4 rounded-3xl border bg-white px-3 py-4"
    >
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2 px-1.5">
          <AI className="text-gray-70 h-7 w-7" />
          <span className="text-heading-large text-gray-70">캐치스턴트 히스토리</span>
        </div>
        <div className="flex gap-1.5">
          <button
            onClick={handleNewQuestion}
            className="capsule-button-outline-blue flex cursor-pointer items-center gap-1.5 px-3 py-1.5"
          >
            <Add className="h-5 w-5 text-blue-50" />
            <span className="text-body-small text-blue-55 relative top-px">새 업무 질문</span>
          </button>
          <button className="icon-button-only-gray cursor-pointer p-1.5">
            <Search className="h-6 w-6" />
          </button>
          <button onClick={onClose} className="icon-button-only-gray cursor-pointer p-1.5">
            <Close className="h-6 w-6" />
          </button>
        </div>
      </div>

      {/* divider */}
      <div className="bg-neutral-3 relative right-3 h-px w-189.25" />

      {/* 질문 목록 */}
      {isLoading ? (
        <div className="text-gray-40 p-5">데이터를 불러오는 중입니다...</div>
      ) : (
        <div className="overflow-y-scroll">
          <SearchHistory querys={recentQueries} isModal={true} onItemClick={onClose} />
        </div>
      )}
    </div>
  );
};

export default RecentQuestionsModal;
