'use client';

import clsx from 'clsx';
import { useState, useRef, useEffect } from 'react';
import Cancel from '/public/icons/icon/cancel.svg';

const feedback = [
  { id: 1, content: '존재하지 않는 자료를 참고했어요' },
  { id: 2, content: '최신 내용이 반영되지 않았어요' },
  { id: 3, content: '답변의 출처가 없어요' },
  { id: 4, content: '중요한 정보가 누락되었어요' },
  { id: 5, content: '유용하지 않은 정보를 참고해요' },
  { id: 6, content: '내가 원하는 내용이 아니에요' },
  { id: 7, content: '답변이 너무 길어요' },
  { id: 8, content: '더 자세히...' },
];

const DETAIL_ID = 8;

const FeedbackSection = ({
  messageId,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
  feedbackSubmittedMap,
  setFeedbackSubmittedMap,
}: FeedbackSectionProps) => {
  const feedbackRef = useRef<HTMLDivElement>(null);

  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailText, setDetailText] = useState('');

  // 피드백 open 시 해당 요소로 하단 스크롤
  useEffect(() => {
    if (feedbackVisibleMap[messageId] && feedbackRef.current) {
      setTimeout(() => {
        feedbackRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
        });
      }, 100);
    }
  }, [feedbackVisibleMap[messageId]]);

  // feedbackSection 닫히면 detail 입력 초기화
  useEffect(() => {
    if (!feedbackVisibleMap[messageId]) {
      setIsDetailOpen(false);
      setDetailText('');
    }
  }, [feedbackVisibleMap[messageId], messageId]);

  if (!feedbackVisibleMap[messageId]) return null;

  const closeSection = () => {
    setFeedbackSubmittedMap((prev) => ({ ...prev, [messageId]: false }));
  };

  const submitFeedback = () => {
    setFeedbackSubmittedMap((prev) => ({ ...prev, [messageId]: true }));

    setTimeout(() => {
      setFeedbackSubmittedMap((prev) => ({ ...prev, [messageId]: false }));
    }, 3000);
  };

  if (!feedbackVisibleMap[messageId]) return null;

  return (
    <div ref={feedbackRef} className="border-neutral-4 mx-auto flex w-193.25 flex-col gap-4 rounded-xl border p-4">
      {feedbackSubmittedMap[messageId] ? (
        <div className="text-body-small flex items-center justify-center text-gray-50">피드백을 주셔서 감사합니다!</div>
      ) : (
        <>
          <div className="flex justify-between">
            <span className="text-body-small text-gray-50">답변이 마음에 들지 않은 이유가 무엇인가요?</span>
            <div
              onClick={closeSection}
              className="icon-button-only-gray flex cursor-pointer items-center rounded-full p-0.5"
            >
              <Cancel className="h-4.5 w-4.5 text-gray-50" />
            </div>
          </div>
          <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
            {feedback.map((feedbackItem) => {
              return (
                <button
                  key={feedbackItem.id}
                  onClick={() => {
                    if (feedbackItem.id === DETAIL_ID) {
                      setIsDetailOpen(true);
                      return;
                    }
                    submitFeedback();
                  }}
                  className={clsx(
                    'box-button-outline-gray text-xsmall text-gray-80 cursor-pointer rounded-lg px-2 py-1',
                    feedbackItem.id === DETAIL_ID && isDetailOpen ? 'bg-neutral-3 border-neutral-5' : '',
                  )}
                >
                  {feedbackItem.content}
                </button>
              );
            })}
          </div>

          {isDetailOpen && (
            <>
              {/* 더 자세히 모달 */}
              <div className="text-body-medium border-blue-30 mt-2.5 flex h-22.25 w-184.75 flex-col rounded-2xl border bg-white px-3 py-2.5">
                <textarea
                  placeholder="자세한 피드백을 남겨주세요."
                  value={detailText}
                  onChange={(e) => setDetailText(e.target.value)}
                  className="text-gray-80 placeholder:text-gray-30 resize-none outline-none"
                />
                <button
                  disabled={!detailText.trim()}
                  onClick={submitFeedback}
                  className={clsx(
                    'text-body-small capsule-button-solid-primary h-9 w-12.5 self-end px-3 py-1.5',
                    detailText.trim() ? 'cursor-pointer' : '',
                  )}
                >
                  제출
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
};

export default FeedbackSection;
