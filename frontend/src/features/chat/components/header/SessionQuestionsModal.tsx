'use client';

import { useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';

import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import { isValidSessionId } from '@/shared/utils/sessionId';

interface SessionQuestionsModalProps {
  onClose: () => void;
  onSelect: (query: string) => void;
}

const SessionQuestionsModal = ({ onClose, onSelect }: SessionQuestionsModalProps) => {
  const params = useParams();
  const sessionIdParam = params.sessionId;
  const sessionId = typeof sessionIdParam === 'string' ? sessionIdParam : '';
  // /chat/new 단계에서는 세션 질문 목록 API를 호출하지 않는다.
  const canLoadSessionQueries = isValidSessionId(sessionId);

  const modalRef = useRef<HTMLDivElement>(null);
  const { data, isLoading } = useQuery({
    ...chatQueries.sessionQueries(sessionId),
    enabled: canLoadSessionQueries,
  });

  const allQueries = data?.items ?? [];

  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      className="shadow-dropdown-menu border-neutral-5 flex max-h-125 w-95 flex-col gap-1.5 overflow-hidden rounded-xl border bg-white py-4"
    >
      {/* 헤더 */}
      <div className="px-5">
        <span className="text-body-small text-gray-50">대화 내 질문 목록</span>
      </div>

      {/* 질문 목록 */}
      <div className="max-h-109.75 w-full overflow-y-auto px-3 py-1.5">
        <div className="flex flex-col gap-1.5">
          {isLoading ? (
            <div className="text-body-small text-gray-40 py-10 text-center">질문을 불러오는 중...</div>
          ) : allQueries.length > 0 ? (
            allQueries.map((item, idx) => (
              <button
                key={idx}
                className="hover:bg-neutral-2 flex h-10 w-full cursor-pointer items-center rounded-xl px-2 py-1 transition-colors"
                onClick={() => {
                  onSelect(item.content);
                  onClose();
                }}
              >
                <span className="text-body-small text-gray-80 truncate text-left">{item.content}</span>
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
