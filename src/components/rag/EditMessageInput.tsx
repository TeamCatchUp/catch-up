'use client';

import clsx from 'clsx';
import { useState, useRef, useEffect } from 'react';

interface EditMessageInputProps {
  initialContent: string;
  onCancel: () => void;
  onSubmit: (newContent: string) => void;
}

const EditMessageInput = ({ initialContent, onCancel, onSubmit }: EditMessageInputProps) => {
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
      const newHeight = Math.min(textAreaRef.current.scrollHeight, 110);
      textAreaRef.current.style.height = newHeight + 'px';
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
      className={clsx(
        'flex flex-col gap-2.5 rounded-2xl border bg-white px-4.5 py-2.5',
        isFocused ? 'border-blue-30' : 'border-neutral-3',
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
        style={{ height: '26px' }}
        className="text-body-medium text-gray-80 box-border w-full resize-none overflow-y-auto px-1 outline-none"
      />
      <div className="flex items-center justify-end gap-2">
        <button
          onClick={onCancel}
          className="capsule-button-outline-mono flex shrink-0 cursor-pointer items-center justify-center px-3 py-1.5"
        >
          <span className="text-body-small text-gray-80">취소</span>
        </button>
        <button
          onClick={handleSubmit}
          disabled={!editText.trim()}
          className="capsule-button-solid-primary flex shrink-0 cursor-pointer items-center justify-center px-3 py-1.5"
        >
          <span className="text-body-small">보내기</span>
        </button>
      </div>
    </div>
  );
};

export default EditMessageInput;
