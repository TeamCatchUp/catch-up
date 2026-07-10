'use client';

import { useEffect, useRef, useState } from 'react';

import { cn } from '@/shared/utils/cn';

const MAX_TEXTAREA_HEIGHT_PX = 200;

interface EditMessageInputProps {
  initialContent: string;
  onCancel: () => void;
  onSubmit: (newContent: string) => Promise<void>;
}

export default function EditMessageInput({ initialContent, onCancel, onSubmit }: EditMessageInputProps) {
  const [editText, setEditText] = useState(initialContent);
  const [isFocused, setIsFocused] = useState(false);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (editText.trim()) {
      onSubmit(editText.trim());
    }
  };

  // textarea 높이 조절
  useEffect(() => {
    if (textAreaRef.current) {
      textAreaRef.current.style.height = 'auto';
      const newHeight = Math.min(textAreaRef.current.scrollHeight, MAX_TEXTAREA_HEIGHT_PX);
      textAreaRef.current.style.height = `${newHeight}px`;
    }
  }, [editText]);

  // textarea 자동 focus
  useEffect(() => {
    if (textAreaRef.current) {
      textAreaRef.current.focus();
      const length = textAreaRef.current.value.length;
      textAreaRef.current.setSelectionRange(length, length);
    }
  }, []);

  return (
    <div
      className={cn(
        'bg-fill-normal-normal flex flex-col gap-2.5 rounded-2xl border-[1.5px] p-4',
        isFocused ? 'border-line-primary-normal' : 'border-line-normal-neutral',
      )}
    >
      <textarea
        ref={textAreaRef}
        value={editText}
        rows={1}
        onChange={(e) => setEditText(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          } else if (e.key === 'Escape') {
            onCancel();
          }
        }}
        className="text-body-small text-text-normal-normal box-border w-full resize-none overflow-y-auto outline-none"
      />
      <div className="flex items-center justify-end gap-2.5">
        <button
          type="button"
          onClick={onCancel}
          className="capsule-button-outline-mono flex shrink-0 cursor-pointer items-center justify-center px-3 py-1.5"
        >
          <span className="text-body-small text-text-normal-normal">취소</span>
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!editText.trim()}
          className="capsule-button-solid-primary flex shrink-0 cursor-pointer items-center justify-center px-3 py-1.5"
        >
          <span className="text-body-small">보내기</span>
        </button>
      </div>
    </div>
  );
}
