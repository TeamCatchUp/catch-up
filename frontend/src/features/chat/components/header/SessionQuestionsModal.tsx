'use client';

import { useEffect, useMemo, useRef } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';

import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { chatQueries } from '@/shared/queries/chatroom.queries';
import { isValidSessionId } from '@/shared/utils/sessionId';

interface SessionQuestionsModalProps {
  sessionId: string;
  onClose: () => void;
  onSelect: (messageId: number) => void;
}

export default function SessionQuestionsModal({ sessionId, onClose, onSelect }: SessionQuestionsModalProps) {
  const canLoadSessionQueries = isValidSessionId(sessionId);

  const modalRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } = useInfiniteQuery({
    ...chatQueries.sessionQueriesInfinite(sessionId),
    enabled: canLoadSessionQueries,
  });

  const allQueries = useMemo(() => data?.pages.flatMap((page) => page.items) ?? [], [data?.pages]);

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

  useEscapeKey(onClose);
  useOutsideClick(modalRef, onClose);

  return (
    <div
      ref={modalRef}
      className="shadow-dropdown-menu border-line-normal-strong bg-fill-normal-normal flex max-h-125 w-95 flex-col gap-1.5 overflow-hidden rounded-xl border py-4"
    >
      {/* 헤더 */}
      <div className="px-5">
        <span className="text-body-small text-text-normal-alternative">대화 내 질문 목록</span>
      </div>

      {/* 질문 목록 */}
      <div className="max-h-109.75 w-full overflow-y-auto px-3 py-1.5">
        <div className="flex flex-col gap-1.5">
          {isLoading ? (
            <div className="text-body-small text-text-normal-assistive py-10 text-center">질문을 불러오는 중...</div>
          ) : allQueries.length > 0 ? (
            allQueries.map((item, idx) => (
              <button
                key={idx}
                className="hover:bg-fill-normal-interaction-hover flex h-10 w-full cursor-pointer items-center rounded-xl px-2 py-1 transition-colors"
                onClick={() => {
                  onSelect(item.id);
                  onClose();
                }}
              >
                <span className="text-body-small text-text-normal-normal truncate text-left">{item.content}</span>
              </button>
            ))
          ) : (
            <div className="text-body-small text-text-normal-assistive py-10 text-center">질문 내역이 없습니다.</div>
          )}
          {isFetchingNextPage && (
            <div className="text-body-small text-text-normal-assistive py-2 text-center">불러오는 중...</div>
          )}
          <div ref={sentinelRef} className="h-1" />
        </div>
      </div>
    </div>
  );
}
