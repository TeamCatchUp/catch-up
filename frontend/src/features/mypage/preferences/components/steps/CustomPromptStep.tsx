'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import IconCopy from '@/public/icons/icon/copy.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import { MAX_PROMPT_LENGTH } from '../../constants/preferencesConfig';
import StepHeader from '../StepHeader';

interface CustomPromptStepProps {
  customPrompt: string | null;
  onSave: (value: string) => void;
  isLoading?: boolean;
}

export default function CustomPromptStep({ customPrompt, onSave, isLoading = false }: CustomPromptStepProps) {
  const hasPrompt = customPrompt !== null;
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState('');
  const [isActive, setIsActive] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isAtLimit = value.length >= MAX_PROMPT_LENGTH;

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  useEffect(() => {
    if (isEditing) {
      adjustHeight();
      textareaRef.current?.focus();
    }
  }, [isEditing, adjustHeight]);

  useEffect(() => {
    if (isActive) adjustHeight();
  }, [value, isActive, adjustHeight]);

  const handleSave = () => {
    onSave(value.trim());
    setIsEditing(false);
    setIsActive(false);
  };

  const handleCancel = () => {
    setValue('');
    setIsEditing(false);
    setIsActive(false);
  };

  const handleCopy = async () => {
    if (!customPrompt) return;
    try {
      await navigator.clipboard.writeText(customPrompt);
    } catch {
      // clipboard API 실패 시 무시 (VPN 환경 등)
    }
  };

  const showInput = !hasPrompt || isEditing;

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5 py-5">
        <StepHeader stepNumber={3} title="커스텀 프롬프트 입력" description="원하는 답변 방식을 직접 입력해보세요." />
        <div className="border-line-normal-neutral bg-fill-normal-normal flex h-11.5 items-center justify-center rounded-xl border">
          <span className="text-body-small text-text-normal-assistive">불러오는 중...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 py-5">
      {/* 헤더 + 편집하기 버튼 */}
      <div className="flex items-end gap-5">
        <div className="flex-1">
          <StepHeader stepNumber={3} title="커스텀 프롬프트 입력" description="원하는 답변 방식을 직접 입력해보세요." />
        </div>
        {hasPrompt && !isEditing && (
          <Button
            type="button"
            variant="box-soft-primary"
            size="md"
            className="shrink-0"
            onClick={() => {
              setValue(customPrompt ?? '');
              setIsEditing(true);
            }}
          >
            편집하기
          </Button>
        )}
      </div>

      {/* 입력 모드 */}
      {showInput && (
        <div
          className={cn(
            'bg-fill-normal-normal w-full rounded-xl border',
            !isActive && !isEditing && 'h-11.5',
            isActive || isEditing
              ? isAtLimit
                ? 'border-status-destructive border-[1.5px]'
                : 'border-line-primary-normal border-[1.5px]'
              : 'border-line-normal-neutral',
          )}
        >
          <div className={cn(isActive || isEditing ? 'px-4.5 py-2.5' : 'p-3')}>
            <textarea
              ref={textareaRef}
              value={value}
              maxLength={MAX_PROMPT_LENGTH}
              onChange={(e) => setValue(e.target.value)}
              onFocus={() => setIsActive(true)}
              onBlur={() => {
                if (value.trim().length === 0) setIsActive(false);
              }}
              placeholder="프로젝트 맥락과 업무 스타일을 반영할 수 있어요."
              rows={1}
              className={cn(
                'text-body-small w-full resize-none bg-transparent outline-none',
                'placeholder:text-text-normal-assistive',
                isActive || isEditing ? 'max-h-50 overflow-y-auto' : 'h-5.5 overflow-hidden',
              )}
            />
            {(isActive || isEditing) && (
              <div className="mt-2.5 flex items-center justify-between">
                <span className={cn('text-label-xsmall', isAtLimit ? 'text-status-destructive' : 'invisible')}>
                  최대 {MAX_PROMPT_LENGTH}자까지 입력할 수 있습니다.
                </span>
                <div className="flex items-center gap-2.5">
                  <Button type="button" variant="capsule-outline-mono" size="md" className="h-9" onClick={handleCancel}>
                    취소
                  </Button>
                  <Button type="button" variant="capsule-solid-primary" size="md" className="h-9" onClick={handleSave}>
                    저장
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 저장된 상태 */}
      {hasPrompt && !isEditing && (
        <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col items-end gap-4 rounded-xl border p-4">
          <div className="max-h-50 w-full overflow-y-auto px-0.5">
            <p className="text-body-small text-text-normal-normal wrap-break-word whitespace-pre-wrap">
              {customPrompt}
            </p>
          </div>
          <Button type="button" variant="box-outline-gray" size="md" onClick={handleCopy}>
            복사하기
            <IconCopy className="size-5" />
          </Button>
        </div>
      )}
    </div>
  );
}
