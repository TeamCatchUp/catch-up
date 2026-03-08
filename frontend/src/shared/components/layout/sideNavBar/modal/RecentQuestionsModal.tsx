'use client';

import { useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import Add from '@/public/icons/icon/add_small.svg';
import AI from '@/public/icons/icon/ai.svg';
import Close from '@/public/icons/icon/cancel.svg';
import Search from '@/public/icons/icon/search.svg';
import { SearchHistory } from '@/shared/components/SearchHistory';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import type { SearchQuery } from '@/shared/types/query/search';
import { formatFullDate } from '@/shared/utils/formatDate';

interface RecentQuestionsModalProps {
  onClose: () => void;
}

type SearchQueryWithRawDate = SearchQuery & { rawDate: Date };

const RecentQuestionsModal = ({ onClose }: RecentQuestionsModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { data, isLoading } = useQuery(chatQueries.recentQueries());

  const recentQueries = useMemo<SearchQueryWithRawDate[]>(() => {
    if (!data?.items) return [];
    return data.items.map((item) => ({
      query: item.content,
      session_id: item.session_id,
      date: formatFullDate(item.created_at),
      rawDate: new Date(item.created_at),
      message_id: item.id,
    }));
  }, [data]);

  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  const handleNewQuestion = () => {
    onClose();
    router.push('/search');
  };

  return (
    <div
      ref={modalRef}
      className="shadow-modal border-edge-normal flex max-h-135 w-190 flex-col gap-4 rounded-3xl border bg-fill-normal px-3 py-4"
    >
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2 px-1.5">
          <AI className="text-icon-normal h-7 w-7" />
          <span className="text-heading-large text-content-neutral">캐치스턴트 히스토리</span>
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
      <div className="bg-edge-neutral relative right-3 h-px w-189.25" />

      {/* 질문 목록 */}
      {isLoading ? (
        <div className="text-content-assistive p-5">데이터를 불러오는 중입니다...</div>
      ) : (
        <div className="overflow-y-scroll">
          <SearchHistory querys={recentQueries} isModal={true} onItemClick={onClose} />
        </div>
      )}
    </div>
  );
};

export default RecentQuestionsModal;
