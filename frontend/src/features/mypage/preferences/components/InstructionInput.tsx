'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import { MAX_INSTRUCTION_LENGTH } from '../constants/preferencesConfig';

interface InstructionInputProps {
  onSave: (value: string) => void;
  defaultValue?: string;
  defaultActive?: boolean;
  onCancelEdit?: () => void;
  isPending?: boolean;
}

const InstructionInput = ({
  onSave,
  defaultValue = '',
  defaultActive = false,
  onCancelEdit,
  isPending = false,
}: InstructionInputProps) => {
  const [value, setValue] = useState(defaultValue);
  const [isActive, setIsActive] = useState(defaultActive);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const isEmpty = value.trim().length === 0;
  const isAtLimit = value.length >= MAX_INSTRUCTION_LENGTH;

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  // 마운트 시 수정 모드면 포커스 + 높이 조정
  useEffect(() => {
    if (defaultActive) {
      adjustHeight();
      textareaRef.current?.focus();
    }
  }, [defaultActive, adjustHeight]);

  // 값 변경 시 높이 자동 조정
  useEffect(() => {
    if (isActive) {
      adjustHeight();
    }
  }, [value, isActive, adjustHeight]);

  const handleFocus = () => {
    setIsActive(true);
  };

  const handleCancel = () => {
    setValue('');
    setIsActive(false);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    onCancelEdit?.();
  };

  const handleSave = () => {
    if (isEmpty) return;
    onSave(value.trim());
    setValue('');
    setIsActive(false);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  return (
    <div
      ref={containerRef}
      className={cn(
        'bg-fill-normal w-full rounded-xl border',
        !isActive && 'h-11.5',
        isActive ? (isAtLimit ? 'border-red-50' : 'border-blue-40') : 'border-edge-neutral',
      )}
    >
      <div className={cn(isActive ? 'px-4.5 py-2.5' : 'p-3')}>
        <textarea
          ref={textareaRef}
          value={value}
          maxLength={MAX_INSTRUCTION_LENGTH}
          onChange={(e) => setValue(e.target.value)}
          onFocus={handleFocus}
          placeholder="프로젝트 맥락과 업무 스타일을 반영할 수 있어요."
          rows={1}
          className={cn(
            'text-body-small w-full resize-none bg-transparent outline-none',
            'placeholder:text-content-assistive',
            isActive ? 'max-h-28.5 overflow-y-auto' : 'h-5.5 overflow-hidden',
          )}
        />
        {isActive && (
          <div className="mt-2.5 flex items-center justify-between">
            <span className={cn('text-label-xsmall', isAtLimit ? 'text-content-assistive' : 'invisible')}>
              최대 1500자까지 입력할 수 있습니다.
            </span>
            <div className="flex items-center gap-2.5">
              <Button type="button" variant="capsule-outline-mono" size="md" className="h-9" onClick={handleCancel}>
                취소
              </Button>
              <Button
                type="button"
                variant="capsule-solid-primary"
                size="md"
                className="h-9"
                disabled={isEmpty || isPending}
                onClick={handleSave}
              >
                {isPending ? '저장 중...' : '저장'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default InstructionInput;
