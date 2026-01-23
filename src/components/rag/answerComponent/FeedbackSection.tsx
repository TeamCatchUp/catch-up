'use client';

import { useRef, useEffect } from 'react';
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

const FeedbackSection = ({
  messageId,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
  feedbackSubmittedMap,
  setFeedbackSubmittedMap,
}: FeedbackSectionProps) => {
  const feedbackRef = useRef<HTMLDivElement>(null);

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
              onClick={() => setFeedbackVisibleMap((prev) => ({ ...prev, [messageId]: false }))}
              className="icon-button-only-gray flex cursor-pointer items-center rounded-full p-0.5"
            >
              <Cancel className="h-4.5 w-4.5 text-gray-50" />
            </div>
          </div>
          <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
            {feedback.map((feedbackItem, feedbackIdx) => {
              return (
                <button
                  key={feedbackIdx}
                  onClick={() => {
                    setFeedbackSubmittedMap((prev) => ({ ...prev, [messageId]: true }));
                    setTimeout(() => {
                      setFeedbackVisibleMap((prev) => ({
                        ...prev,
                        [messageId]: false,
                      }));
                    }, 3000);
                  }}
                  className="box-button-outline-gray border-neutral-3 text-xsmall text-gray-80 cursor-pointer rounded-lg border px-2 py-1"
                >
                  {feedbackItem.content}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

export default FeedbackSection;
