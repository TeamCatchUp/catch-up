'use client';

import { RefObject, useEffect, useMemo, useRef } from 'react';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';

interface QueryInputProps {
  input: UseSearchInputReturn;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  highlightBracketPlaceholders?: boolean;
}

const BRACKET_PLACEHOLDER_REGEX = /(\[[^\]]+\])/g;

interface HighlightSegment {
  text: string;
  isPlaceholder: boolean;
}

const splitByBracketPlaceholders = (value: string): HighlightSegment[] =>
  value
    .split(BRACKET_PLACEHOLDER_REGEX)
    .filter((segment) => segment.length > 0)
    .map((segment) => ({
      text: segment,
      isPlaceholder: segment.startsWith('[') && segment.endsWith(']'),
    }));

export default function QueryInput({
  input,
  inputRef,
  highlightBracketPlaceholders = false,
}: QueryInputProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const shouldHighlight = highlightBracketPlaceholders && input.value.length > 0;

  const highlightedSegments = useMemo(
    () => (shouldHighlight ? splitByBracketPlaceholders(input.value) : []),
    [shouldHighlight, input.value],
  );

  useEffect(() => {
    if (!shouldHighlight || !overlayRef.current || !inputRef.current) return;
    overlayRef.current.scrollTop = inputRef.current.scrollTop;
    overlayRef.current.scrollLeft = inputRef.current.scrollLeft;
  }, [input.value, shouldHighlight, inputRef]);

  const syncOverlayScroll = () => {
    if (!overlayRef.current || !inputRef.current) return;
    overlayRef.current.scrollTop = inputRef.current.scrollTop;
    overlayRef.current.scrollLeft = inputRef.current.scrollLeft;
  };

  return (
    <div className="flex w-full items-center justify-between">
      <div className="text-button-secondary-mono mr-2 flex h-10 w-10 cursor-pointer items-center justify-center p-1.5">
        <IconAdd className="text-gray-70 h-7 w-7" />
      </div>
      <div className="relative flex flex-1">
        {shouldHighlight && (
          <div
            ref={overlayRef}
            aria-hidden
            className="text-body-medium pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words text-gray-70"
          >
            {highlightedSegments.map((segment, index) => (
              <span key={`${segment.text}-${index}`} className={segment.isPlaceholder ? 'text-blue-50' : ''}>
                {segment.text}
              </span>
            ))}
          </div>
        )}
        <textarea
          ref={inputRef}
          rows={1}
          className={`text-body-medium w-full resize-none outline-none ${
            shouldHighlight ? 'relative z-10 bg-transparent text-transparent caret-gray-70' : ''
          }`}
          placeholder="업무와 관련해 궁금한 무엇이든 물어보세요!"
          value={input.value}
          onFocus={() => input.setIsFocused(true)}
          onScroll={syncOverlayScroll}
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
        className={`rounded-rounded ml-2 flex items-center border border-solid p-2 ${
          input.hasText ? 'cursor-pointer border-blue-50 bg-blue-50' : 'bg-neutral-1 border-neutral-2'
        }`}
      >
        <IconArrowSend className={`${input.hasText ? 'brightness-0 invert' : 'text-gray-30'} h-6 w-6`} />
      </button>
    </div>
  );
}
