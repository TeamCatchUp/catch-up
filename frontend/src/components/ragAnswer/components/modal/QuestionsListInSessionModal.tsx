'use client';

import { useState, useRef, useEffect } from 'react';
import { useParams } from 'next/navigation'; // URL에서 sessionId를 가져오기 위함
import List from '/public/icons/icon/list.svg';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';
import { nowChatroomService } from '@/api/search';

interface QuestionsListInSessionModalProps {
  onClose: () => void;
  onSelect: (query: string) => void;
}

// 인터페이스 정의 수정
interface ChatQuery {
  query: string;
}

const QuestionsListInSessionModal = ({ onClose, onSelect }: QuestionsListInSessionModalProps) => {
  const params = useParams();
  const sessionId = params.sessionId as string; // URL 구조가 /ragAnswer/[sessionId] 인 경우

  const [allQueries, setAllQueries] = useState<ChatQuery[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchDefaultData = async () => {
      if (!sessionId) return;

      try {
        setIsLoading(true);
        // 이전에 고친 서비스 함수를 호출 (sessionId 전달)
        const res = await nowChatroomService.getAllQueries(sessionId);

        // 백엔드 응답 구조가 { content: [ { query: '...' }, ... ] } 인 경우
        if (res && res.content) {
          setAllQueries(res.content);
        } else if (Array.isArray(res)) {
          // 응답이 바로 배열인 경우 대비
          setAllQueries(res.map((q: any) => (typeof q === 'string' ? { query: q } : q)));
        }
      } catch (err) {
        console.error('데이터 로드 실패:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDefaultData();
  }, [sessionId]);

  // Hook 규칙 준수: Early Return(isLoading)보다 위에서 호출
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
                  /* 필요한 경우 해당 질문 위치로 스크롤 등 액션 추가 */
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

export default QuestionsListInSessionModal;
