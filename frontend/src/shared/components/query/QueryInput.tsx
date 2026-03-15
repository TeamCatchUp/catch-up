'use client';

import { RefObject, useCallback, useRef } from 'react';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';
import type { TipData } from '@/shared/types/template';
import { cn } from '@/shared/utils/cn';

import TemplateInput from './TemplateInput';

interface QueryInputProps {
  input: UseSearchInputReturn;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  highlightBracketPlaceholders?: boolean;
  tipData?: TipData[];
}

export default function QueryInput({ input, inputRef, tipData }: QueryInputProps) {
  const submitButtonRef = useRef<HTMLButtonElement>(null);
  const isTemplateMode = input.isFromTemplate && input.selectedTipIndex !== null && !!tipData;

  // Lexical TemplateInput에서 준비된 submit 함수를 저장
  const templateSubmitRef = useRef<(() => void) | null>(null);
  const handleTemplateSubmitReady = useCallback((fn: () => void) => {
    templateSubmitRef.current = fn;
  }, []);

  const handleSubmitClick = useCallback(() => {
    if (isTemplateMode && templateSubmitRef.current) {
      templateSubmitRef.current();
    } else {
      input.handleSubmit();
    }
  }, [isTemplateMode, input]);

  return (
    <div className="flex w-full items-center justify-between">
      <div className="text-button-secondary-mono mr-2 flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center self-end p-1.5">
        <IconAdd className="text-icon-normal h-7 w-7" />
      </div>
      <div className="relative flex flex-1">
        {isTemplateMode ? (
          <TemplateInput
            tip={tipData[input.selectedTipIndex!]}
            input={input}
            submitButtonRef={submitButtonRef}
            onSubmitReady={handleTemplateSubmitReady}
          />
        ) : (
          <textarea
            ref={inputRef}
            rows={1}
            className={cn('text-body-medium w-full resize-none outline-none', input.isFromTemplate && 'leading-[1.7]')}
            placeholder="업무와 관련해 궁금한 무엇이든 물어보세요!"
            value={input.value}
            onFocus={() => input.setIsFocused(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                input.handleSubmit();
              }
            }}
            onChange={(e) => {
              input.setIsFromTemplate(false);
              input.setSelectedTipIndex(null);
              input.resetTemplateFields();
              input.setValue(e.target.value);
            }}
          />
        )}
      </div>
      <button
        ref={submitButtonRef}
        onClick={handleSubmitClick}
        className={`rounded-rounded ml-2 flex shrink-0 items-center self-end border border-solid p-2 ${
          input.hasText ? 'border-fill-primary bg-fill-primary cursor-pointer' : 'bg-fill-strong border-edge-assistive'
        }`}
      >
        <IconArrowSend className={`${input.hasText ? 'brightness-0 invert' : 'text-content-assistive'} h-6 w-6`} />
      </button>
    </div>
  );
}
