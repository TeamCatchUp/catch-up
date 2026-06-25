'use client';

import { useCallback, useEffect, useRef } from 'react';

import { cn } from '@/shared/utils/cn';

const TEXTAREA_MAX_HEIGHT = 114;

interface FeedbackDetailInputProps {
  detailText: string;
  onDetailChange: (text: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isSubmitting: boolean;
  entered: boolean;
}

export default function FeedbackDetailInput({
  detailText,
  onDetailChange,
  onSubmit,
  onCancel,
  isSubmitting,
  entered,
}: FeedbackDetailInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;

    el.style.height = 'auto';
    const next = Math.min(el.scrollHeight, TEXTAREA_MAX_HEIGHT);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > TEXTAREA_MAX_HEIGHT ? 'auto' : 'hidden';
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [detailText, resizeTextarea]);

  return (
    <div
      className={cn(
        'border-line-primary-normal bg-fill-normal-normal flex w-full flex-col gap-2.5 rounded-2xl border px-4.5 py-2.5',
        'transition-all duration-200 ease-out will-change-[transform,opacity]',
        entered ? 'translate-y-0 scale-100 opacity-100' : '-translate-y-1 scale-[0.99] opacity-0',
      )}
    >
      <textarea
        ref={textareaRef}
        placeholder="자세한 피드백을 남겨주세요."
        value={detailText}
        onChange={(e) => {
          onDetailChange(e.target.value);
          requestAnimationFrame(resizeTextarea);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSubmit();
          }
        }}
        className="text-body-medium text-text-normal-normal placeholder:text-text-normal-assistive w-full resize-none overflow-y-hidden outline-none"
        style={{ maxHeight: `${TEXTAREA_MAX_HEIGHT}px` }}
        rows={1}
      />
      <div className="flex items-center justify-end gap-2">
        <button
          onClick={onCancel}
          className="capsule-button-outline-mono flex shrink-0 cursor-pointer items-center justify-center px-3 py-1.5"
        >
          <span className="text-body-small text-text-normal-normal">취소</span>
        </button>
        <button
          disabled={!detailText.trim() || isSubmitting}
          onClick={onSubmit}
          className={cn(
            'capsule-button-solid-primary flex shrink-0 items-center justify-center px-3 py-1.5',
            detailText.trim() ? 'cursor-pointer' : '',
          )}
        >
          <span className="text-body-small">제출</span>
        </button>
      </div>
    </div>
  );
}
