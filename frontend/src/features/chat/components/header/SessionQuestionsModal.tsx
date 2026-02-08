'use client';

import { useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';

import { chatQueries } from '@/shared/queries/chatroom.queries';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';

import List from '/public/icons/icon/list.svg';

interface SessionQuestionsModalProps {
  onClose: () => void;
  onSelect: (query: string) => void;
}

const SessionQuestionsModal = ({ onClose, onSelect }: SessionQuestionsModalProps) => {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const modalRef = useRef<HTMLDivElement>(null);
  const { data, isLoading } = useQuery(chatQueries.sessionQueries(sessionId));

  const allQueries = data?.content ?? [];

  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      className="shadow-dropdown-menu border-neutral-5 flex max-h-125 w-95 flex-col gap-4 rounded-2xl border bg-white py-4"
    >
      {/* 헤더 */}
      <div className="flex items-center gap-2 px-5">
        <List className="text-gray-70 h-6 w-6" />
        <span className="text-heading-medium text-gray-80 relative top-px">대화 내 질문 목록</span>
        <span className="text-heading-medium text-blue-55 relative top-px">{isLoading ? '-' : allQueries.length}</span>
      </div>

      {/* 질문 목록 */}
      <div className="border-t-neutral-3 custom-scrollbar overflow-y-auto border-t pt-3">
        <div className="flex flex-col gap-2 px-4">
          {isLoading ? (
            <div className="text-body-small text-gray-40 py-10 text-center">질문을 불러오는 중...</div>
          ) : allQueries.length > 0 ? (
            allQueries.map((item, idx) => (
              <button
                key={idx}
                className="hover:bg-neutral-1 rounded-md2 flex h-10 w-full cursor-pointer items-center px-2.5 py-1 transition-colors"
                onClick={() => {
                  onSelect(item.query);
                  onClose();
                }}
              >
                <span className="text-body-small text-gray-80 truncate text-left">{item.query}</span>
              </button>
            ))
          ) : (
            <div className="text-body-small text-gray-40 py-10 text-center">질문 내역이 없습니다.</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SessionQuestionsModal;
