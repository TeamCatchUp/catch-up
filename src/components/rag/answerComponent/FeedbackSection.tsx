'use client';

import clsx from 'clsx';
import { useState, useRef, useEffect, useCallback } from 'react';
import Cancel from '/public/icons/icon/cancel.svg';
import { sendFeedbackQuery } from '@/api/feedback';

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
const TEXTAREA_MAX_HEIGHT = 114;
const THANKS_MESSAGE_DURATION = 3000;

const FeedbackSection = ({
  messageId,
  chatHistoryId,
  hasFeedback,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
  onFeedbackSubmitted,
}: FeedbackSectionProps) => {
  const feedbackRef = useRef<HTMLDivElement>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailText, setDetailText] = useState('');
  const [showThanks, setShowThanks] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localHasFeedback, setLocalHasFeedback] = useState(hasFeedback);

  // hasFeedback prop 변경 되면 로컬 상태도 업데이트
  useEffect(() => {
    setLocalHasFeedback(hasFeedback);
  }, [hasFeedback]);

  // textarea 자동 높이 조절
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;

    el.style.height = 'auto';
    const next = Math.min(el.scrollHeight, TEXTAREA_MAX_HEIGHT);
    el.style.height = `${next}px`;

    // max 넘어가면 내부 스크롤
    el.style.overflowY = el.scrollHeight > TEXTAREA_MAX_HEIGHT ? 'auto' : 'hidden';
  }, []);

  // text 변경 시 resize
  useEffect(() => {
    if (!isDetailOpen) return;
    resizeTextarea();
  }, [detailText, isDetailOpen, resizeTextarea]);

  // 피드백 open 시 해당 요소로 하단 스크롤
  useEffect(() => {
    if (feedbackVisibleMap[messageId] && feedbackRef.current) {
      setTimeout(() => {
        feedbackRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'end',
        });
      }, 100);
    }
  }, [feedbackVisibleMap[messageId]]);

  // 더 자세히 모달 open 시 해당 요소로 하단 스크롤
  useEffect(() => {
    if (isDetailOpen && detailRef.current) {
      setTimeout(() => {
        detailRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'end',
        });
      }, 100);
    }
  }, [isDetailOpen]);

  // feedbackSection 닫히면 detail 입력 초기화
  useEffect(() => {
    if (!feedbackVisibleMap[messageId]) {
      setIsDetailOpen(false);
      setDetailText('');
      setShowThanks(false);
      setIsSubmitting(false);
    }
  }, [feedbackVisibleMap[messageId], messageId]);

  // 피드백 제출 완 -> 자동 감사 UI
  useEffect(() => {
    if (!feedbackVisibleMap[messageId]) return;

    if (hasFeedback) {
      const timer = setTimeout(() => {
        setShowThanks(true);
      }, THANKS_MESSAGE_DURATION);

      return () => clearTimeout(timer);
    }
  }, [hasFeedback, feedbackVisibleMap, messageId]);

  const closeSection = useCallback(() => {
    setIsDetailOpen(false);
    setDetailText('');
    setFeedbackVisibleMap((prev) => ({ ...prev, [messageId]: false }));
  }, [messageId, setFeedbackVisibleMap]);

  const afterSuccessClose = useCallback(() => {
    setTimeout(() => {
      setShowThanks(false);
      setFeedbackVisibleMap((prev) => ({ ...prev, [messageId]: false }));
    }, THANKS_MESSAGE_DURATION);
  }, [messageId, setFeedbackVisibleMap]);

  const submitFeedback = useCallback(
    async (selectedContent?: string) => {
      if (!chatHistoryId) {
        console.warn('[feedback] chatHistoryId missing');
        setLocalHasFeedback(true);
        setShowThanks(true);
        afterSuccessClose();
        return;
      }

      if (isSubmitting) return;

      const isDetail = isDetailOpen;

      const tags = selectedContent ? [selectedContent] : [];
      const detail = isDetail ? detailText.trim() : '';

      // detail 모드인데 비어있으면 제출 막기
      if (isDetail && !detail) return;

      try {
        setIsSubmitting(true);

        console.log('[submitFeedback] send', {
          chatHistoryId,
          tags,
          detail,
        });

        await sendFeedbackQuery({
          chatHistoryId,
          tags,
          detail,
        });

        setLocalHasFeedback(true);

        // 부모 컴포넌트에 알림
        if (onFeedbackSubmitted) {
          onFeedbackSubmitted(messageId);
        }

        setShowThanks(true);
        afterSuccessClose();
      } catch (e) {
        console.error('[feedback] submit failed', e);
        // 실패 시에도 이미 제출된 경우라면 감사 메시지 표시
        const error = e as any;
        if (error?.response?.status === 500) {
          // 500 에러 = 이미 제출된 피드백
          console.warn('[feedback] Already submitted, showing thanks message');
          setLocalHasFeedback(true);

          if (onFeedbackSubmitted) {
            onFeedbackSubmitted(messageId);
          }

          setShowThanks(true);
          afterSuccessClose();
        }
        // 그 외 에러는 사용자가 다시 시도할 수 있도록 유지
      } finally {
        setIsSubmitting(false);
      }
    },
    [chatHistoryId, detailText, isDetailOpen, isSubmitting, afterSuccessClose, onFeedbackSubmitted, messageId],
  );

  if (!feedbackVisibleMap[messageId]) return null;

  // 이미 피드백 제출 / 방금 제출 -> 감사 UI
  if (localHasFeedback || showThanks) {
    return (
      <div ref={feedbackRef} className="border-neutral-4 mx-auto flex w-193.25 flex-col gap-4 rounded-xl border p-4">
        <div className="text-body-small flex items-center justify-center text-gray-50">피드백을 주셔서 감사합니다!</div>
      </div>
    );
  }

  return (
    <div ref={feedbackRef} className="border-neutral-4 mx-auto flex w-193.25 flex-col gap-4 rounded-xl border p-4">
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
              disabled={isSubmitting}
              onClick={() => {
                if (feedbackItem.id === DETAIL_ID) {
                  setIsDetailOpen((prev) => {
                    const next = !prev;
                    if (!next) setDetailText(''); // 닫히면 입력 초기화
                    return next;
                  });
                  return;
                }
                submitFeedback(feedbackItem.content);
              }}
              className={clsx(
                'text-xsmall text-gray-80 cursor-pointer rounded-lg px-2 py-1',
                feedbackItem.id === DETAIL_ID && isDetailOpen
                  ? 'bg-neutral-3 border-neutral-5'
                  : 'box-button-outline-gray',
              )}
            >
              {feedbackItem.content}
            </button>
          );
        })}
      </div>

      {/* 더 자세히 모달 */}
      {isDetailOpen && (
        <div
          ref={detailRef}
          className="text-body-medium border-blue-30 flex w-184.75 flex-col rounded-2xl border bg-white px-3 py-2.5"
        >
          <textarea
            ref={textareaRef}
            placeholder="자세한 피드백을 남겨주세요."
            value={detailText}
            onChange={(e) => {
              setDetailText(e.target.value);
              requestAnimationFrame(resizeTextarea);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitFeedback();
              }
            }}
            className="text-gray-80 placeholder:text-gray-30 resize-none overflow-y-hidden outline-none"
            style={{ maxHeight: `${TEXTAREA_MAX_HEIGHT}px` }}
            rows={1}
          />
          <button
            disabled={!detailText.trim() || isSubmitting}
            onClick={() => submitFeedback()}
            className={clsx(
              'capsule-button-solid-primary h-9 w-12.5 items-end self-end px-3 py-1.5',
              detailText.trim() ? 'cursor-pointer' : '',
            )}
          >
            <span className="text-body-small">제출</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default FeedbackSection;
