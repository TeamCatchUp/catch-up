'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

interface AgentInstructionFieldProps {
  value: string;
  onChange: (value: string) => void;
  hintText: string;
  disabled?: boolean;
}

export default function AgentInstructionField({
  value,
  onChange,
  hintText,
  disabled = false,
}: AgentInstructionFieldProps) {
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isActive = isFocused;
  const borderColor = isActive ? 'var(--line-primary-normal)' : 'var(--line-neutral)';
  const borderWidth = isActive ? 1.5 : 1;

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [adjustHeight, value]);

  return (
    <label className="flex w-full flex-col gap-3">
      <span className="text-heading-small text-text-normal-normal flex items-start gap-1">
        답변 초안, 어떤 규칙으로 쓸까요?
      </span>
      <div
        className="bg-fill-normal-normal flex min-h-24.5 w-full items-start rounded-xl border border-solid p-4 transition-colors"
        style={{ borderColor, borderWidth }}
      >
        <div className="min-w-0 flex-1 overflow-hidden px-0.5">
          <textarea
            aria-label="답변 초안, 어떤 규칙으로 쓸까요?"
            ref={textareaRef}
            className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive max-h-50 min-h-5.75 w-full resize-none overflow-y-auto bg-transparent p-0 leading-normal outline-none"
            disabled={disabled}
            placeholder={hintText}
            rows={1}
            value={value}
            onBlur={() => setIsFocused(false)}
            onChange={(event) => onChange(event.target.value)}
            onFocus={() => {
              setIsFocused(true);
              adjustHeight();
            }}
          />
        </div>
      </div>
    </label>
  );
}
