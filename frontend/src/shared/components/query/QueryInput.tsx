'use client';

import { RefObject } from 'react';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';

interface QueryInputProps {
  input: UseSearchInputReturn;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}

export default function QueryInput({ input, inputRef }: QueryInputProps) {
  return (
    <div className="flex w-full items-end justify-between">
      <div className="text-button-secondary-mono relative bottom-0.5 mr-2 flex h-10 w-10 cursor-pointer items-center justify-center p-1.5">
        <IconAdd className="text-gray-70 h-7 w-7" />
      </div>
      <div className="flex flex-1 items-center gap-2">
        <textarea
          ref={inputRef}
          rows={1}
          className="text-body-medium mb-2.25 w-full resize-none outline-none"
          placeholder="업무와 관련해 궁금한 무엇이든 물어보세요!"
          value={input.value}
          onFocus={() => input.setIsFocused(true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              input.handleSubmit();
            }
          }}
          onChange={(e) => input.setValue(e.target.value)}
        />
      </div>
      <button
        onClick={input.handleSubmit}
        className={`rounded-rounded relative bottom-px ml-2 flex items-center border border-solid p-2 ${
          input.hasText ? 'cursor-pointer border-blue-50 bg-blue-50' : 'bg-neutral-1 border-neutral-2'
        }`}
      >
        <IconArrowSend className={`${input.hasText ? 'brightness-0 invert' : 'text-gray-30'} h-6 w-6`} />
      </button>
    </div>
  );
}
