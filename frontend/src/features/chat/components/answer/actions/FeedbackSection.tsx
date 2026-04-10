'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { useScrollIntoContainer } from '@/features/chat/hooks/scroll/useScrollIntoContainer';
import { useAnimatedMount } from '@/features/chat/hooks/ui/useAnimatedMount';
import { chatMutations } from '@/features/chat/mutations';
import type { FeedbackReason } from '@/features/chat/types/api/feedbackApi';
import type { FeedbackSectionProps } from '@/features/chat/types/props/actionProps';
import Cancel from '@/public/icons/icon/cancel.svg';
import { cn } from '@/shared/utils/cn';

import FeedbackDetailInput from './FeedbackDetailInput';

const FEEDBACK_CHIPS: { id: number; label: string; reason: FeedbackReason }[] = [
  { id: 1, label: '존재하지 않는 자료를 참고했어요', reason: 'HALLUCINATION' },
  { id: 2, label: '최신 내용이 반영되지 않았어요', reason: 'OUTDATED' },
  { id: 3, label: '답변의 출처가 없어요', reason: 'NO_CITATION' },
  { id: 4, label: '중요한 정보가 누락되었어요', reason: 'MISSING_INFO' },
  { id: 5, label: '유용하지 않은 정보를 참고해요', reason: 'IRRELEVANT_SOURCE' },
  { id: 6, label: '내가 원하는 내용이 아니에요', reason: 'IRRELEVANT_ANSWER' },
  { id: 7, label: '답변이 너무 길어요', reason: 'TOO_LONG' },
  { id: 8, label: '더 자세히...', reason: 'OTHER' },
];

const DETAIL_ID = 8;
const ANIM_MS = 200;

export default function FeedbackSection({
  messageId,
  sessionId,
  chatHistoryId,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
  onFeedbackSubmitted,
}: FeedbackSectionProps) {
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
  const [submitError, setSubmitError] = useState(false);

  const isSubmitting = feedbackMutation.isPending;
  const isVisible = !!feedbackVisibleMap[messageId];

  // 애니메이션
  const section = useAnimatedMount(isVisible, ANIM_MS);
  const detail = useAnimatedMount(isDetailOpen, ANIM_MS);

  // 스크롤
  const scrollSection = useScrollIntoContainer(feedbackRef, 80);
  const scrollDetail = useScrollIntoContainer(detailRef, 100);

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
    onFeedbackSubmitted?.(messageId, false);
    toast('피드백을 주셔서 감사합니다.');
    closeSection();
  }, [messageId, onFeedbackSubmitted, closeSection]);

  // 피드백 제출
  const submitFeedback = useCallback(
    async (selectedReason?: FeedbackReason) => {
      if (!chatHistoryId) {
        console.warn('[feedback] chatHistoryId(message_id) missing — 피드백 제출 불가');
        toast('피드백을 제출할 수 없습니다.');
        return;
      }

      if (isSubmitting) return;

      const isDetail = isDetailOpen;
      const reasons: FeedbackReason[] = selectedReason ? [selectedReason] : [];
      const comment = isDetail ? detailText.trim() : null;

      // OTHER 선택 시 comment 필수
      if (selectedReason === 'OTHER' && !comment) return;

      setSubmitError(false);

      try {
        await feedbackMutationRef.current.mutateAsync({
          params: { sessionId, messageId: chatHistoryId },
          body: { is_liked: false, reasons, comment },
        });

        handleSubmitSuccess();
      } catch (e) {
        console.error('[feedback] submit failed', e);
        setSubmitError(true);
      } finally {
        feedbackMutationRef.current.reset();
      }
    },
    [chatHistoryId, sessionId, detailText, isDetailOpen, isSubmitting, handleSubmitSuccess],
  );

  if (!section.mounted) return null;

  const rootClass = cn(
    'border-edge-neutral mx-auto flex w-193.25 flex-col gap-4 rounded-xl border p-4',
    'transition-all duration-200 ease-out will-change-[transform,opacity]',
    section.entered ? 'translate-y-0 opacity-100' : '-translate-y-2 opacity-0',
  );

  return (
    <div ref={feedbackRef} className={rootClass}>
      <div className="flex justify-between">
        <span className="text-body-small text-content-alternative">답변이 마음에 들지 않은 이유가 무엇인가요?</span>
        <div
          onClick={closeSection}
          className="icon-button-only-gray flex cursor-pointer items-center rounded-full p-0.5"
        >
          <Cancel className="text-content-alternative h-4.5 w-4.5" />
        </div>
      </div>
      <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
        {FEEDBACK_CHIPS.map((chip) => (
          <button
            key={chip.id}
            disabled={isSubmitting || (isDetailOpen && chip.id !== DETAIL_ID)}
            onClick={() => {
              if (chip.id === DETAIL_ID) {
                setIsDetailOpen((prev) => {
                  if (prev) setDetailText('');
                  return !prev;
                });
                return;
              }
              setSelectedChipId(chip.id);
              submitFeedback(chip.reason);
            }}
            className={cn(
              'text-xsmall text-content-normal cursor-pointer rounded-lg px-2 py-1',
              (chip.id === DETAIL_ID && isDetailOpen) || chip.id === selectedChipId
                ? 'bg-fill-interaction-pressed border-edge-strong'
                : 'box-button-outline-gray',
            )}
          >
            {chip.label}
          </button>
        ))}
      </div>

      {submitError && (
        <p className="text-xsmall text-status-destructive">피드백 제출에 실패했습니다. 다시 시도해주세요.</p>
      )}

      {detail.mounted && (
        <div ref={detailRef}>
          <FeedbackDetailInput
            detailText={detailText}
            onDetailChange={setDetailText}
            onSubmit={() => submitFeedback('OTHER')}
            onCancel={() => setIsDetailOpen(false)}
            isSubmitting={isSubmitting}
            entered={detail.entered}
          />
        </div>
      )}
    </div>
  );
}
