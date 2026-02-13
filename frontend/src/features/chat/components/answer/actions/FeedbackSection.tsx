'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { useScrollIntoContainer } from '@/features/chat/hooks/scroll/useScrollIntoContainer';
import { useAnimatedMount } from '@/features/chat/hooks/ui/useAnimatedMount';
import { chatMutations } from '@/features/chat/mutations';
import type { FeedbackSectionProps } from '@/features/chat/types/props/actionProps';
import { cn } from '@/shared/utils/cn';

import FeedbackDetailInput from './FeedbackDetailInput';

import Cancel from '/public/icons/icon/cancel.svg';

const FEEDBACK_CHIPS = [
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
const ANIM_MS = 200;

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

  // 뮤테이션
  const feedbackMutation = useMutation({
    ...chatMutations.sendFeedback(),
    meta: { skipGlobalErrorHandler: true },
  });
  const feedbackMutationRef = useRef(feedbackMutation);
  feedbackMutationRef.current = feedbackMutation;

  // 상태
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailText, setDetailText] = useState('');
  const [selectedChipId, setSelectedChipId] = useState<number | null>(null);
  const [localHasFeedback, setLocalHasFeedback] = useState(hasFeedback);

  const isSubmitting = feedbackMutation.isPending;
  const isVisible = !!feedbackVisibleMap[messageId];

  // 애니메이션
  const section = useAnimatedMount(isVisible, ANIM_MS);
  const detail = useAnimatedMount(isDetailOpen, ANIM_MS);

  // 스크롤
  const scrollSection = useScrollIntoContainer(feedbackRef, 80);
  const scrollDetail = useScrollIntoContainer(detailRef, 100);

  // hasFeedback prop 동기화
  useEffect(() => {
    setLocalHasFeedback(hasFeedback);
  }, [hasFeedback]);

  // 섹션 닫힐 때 상태 초기화
  useEffect(() => {
    if (!isVisible) {
      setIsDetailOpen(false);
      setDetailText('');
      setSelectedChipId(null);
      feedbackMutationRef.current.reset();
    }
  }, [isVisible]);

  // 섹션 열릴 때 스크롤
  useEffect(() => {
    if (section.mounted && section.entered) scrollSection();
  }, [section.mounted, section.entered, scrollSection]);

  // detail 열릴 때 스크롤
  useEffect(() => {
    if (detail.mounted && detail.entered) {
      setTimeout(scrollDetail, ANIM_MS + 50);
    }
  }, [detail.mounted, detail.entered, scrollDetail]);

  // 닫기
  const closeSection = useCallback(() => {
    setIsDetailOpen(false);
    setDetailText('');
    setFeedbackVisibleMap((prev) => ({ ...prev, [messageId]: false }));
  }, [messageId, setFeedbackVisibleMap]);

  // 제출 성공 처리
  const handleSubmitSuccess = useCallback(() => {
    setLocalHasFeedback(true);
    onFeedbackSubmitted?.(messageId);
    toast('피드백을 주셔서 감사합니다.');
    closeSection();
  }, [messageId, onFeedbackSubmitted, closeSection]);

  // 피드백 제출
  const submitFeedback = useCallback(
    async (selectedContent?: string) => {
      if (!chatHistoryId) {
        console.warn('[feedback] chatHistoryId missing');
        handleSubmitSuccess();
        return;
      }

      if (isSubmitting || localHasFeedback) return;

      const isDetail = isDetailOpen;
      const tags = selectedContent ? [selectedContent] : [];
      const detailValue = isDetail ? detailText.trim() : '';

      if (isDetail && !detailValue) return;

      try {
        await feedbackMutationRef.current.mutateAsync({
          chat_history_id: chatHistoryId,
          tags,
          detail: detailValue,
        });

        handleSubmitSuccess();
      } catch (e) {
        console.error('[feedback] submit failed', e);
        const error = e as { response?: { status?: number } };
        if (error?.response?.status === 500) {
          // 500 에러 = 이미 제출된 피드백
          handleSubmitSuccess();
        }
      } finally {
        feedbackMutationRef.current.reset();
      }
    },
    [chatHistoryId, detailText, isDetailOpen, isSubmitting, localHasFeedback, handleSubmitSuccess],
  );

  if (!section.mounted || localHasFeedback) return null;

  const rootClass = cn(
    'border-neutral-3 mx-auto flex w-193.25 flex-col gap-4 rounded-xl border p-4',
    'transition-all duration-200 ease-out will-change-[transform,opacity]',
    section.entered ? 'translate-y-0 opacity-100' : '-translate-y-2 opacity-0',
  );

  return (
    <div ref={feedbackRef} className={rootClass}>
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
        {FEEDBACK_CHIPS.map((chip) => (
          <button
            key={chip.id}
            disabled={isSubmitting}
            onClick={() => {
              if (chip.id === DETAIL_ID) {
                setIsDetailOpen((prev) => {
                  if (prev) setDetailText('');
                  return !prev;
                });
                return;
              }
              setSelectedChipId(chip.id);
              submitFeedback(chip.content);
            }}
            className={cn(
              'text-xsmall text-gray-80 cursor-pointer rounded-lg px-2 py-1',
              (chip.id === DETAIL_ID && isDetailOpen) || chip.id === selectedChipId
                ? 'bg-neutral-3 border-neutral-5'
                : 'box-button-outline-gray',
            )}
          >
            {chip.content}
          </button>
        ))}
      </div>

      {detail.mounted && (
        <div ref={detailRef}>
          <FeedbackDetailInput
            detailText={detailText}
            onDetailChange={setDetailText}
            onSubmit={() => submitFeedback()}
            onCancel={() => setIsDetailOpen(false)}
            isSubmitting={isSubmitting}
            entered={detail.entered}
          />
        </div>
      )}
    </div>
  );
};

export default FeedbackSection;
