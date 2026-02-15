'use client';

import { useRef, useState } from 'react';

import { useIsOverflowingLines } from '@/features/chat/hooks/ui/useIsOverflowingLines';
import { cn } from '@/shared/utils/cn';

import DropdownDown from '/public/icons/icon/dropdown_down.svg';
import DropdownUp from '/public/icons/icon/dropdown_up.svg';

interface CollapsibleQuestionTextProps {
  content: string;
}

const CollapsibleQuestionText = ({ content }: CollapsibleQuestionTextProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const measureRef = useRef<HTMLParagraphElement>(null);
  const isExpandable = useIsOverflowingLines({
    elementRef: measureRef,
    lineCount: 2,
    watch: content,
  });

  return (
    <>
      <p
        ref={measureRef}
        aria-hidden
        className="text-heading-xlarge text-gray-70 pointer-events-none invisible absolute top-0 left-0 w-full pr-6"
      >
        {content}
      </p>

      {isExpandable ? (
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          aria-expanded={isExpanded}
          aria-label={isExpanded ? '질문 접기' : '질문 펼치기'}
          className="block w-full cursor-pointer text-left"
        >
          <p className={cn('text-heading-xlarge text-gray-70 pr-6', !isExpanded && 'line-clamp-2')}>{content}</p>
          <span className="absolute right-0 bottom-1.5">
            {isExpanded ? (
              <DropdownUp className="text-gray-70 h-5 w-5" />
            ) : (
              <DropdownDown className="text-gray-70 h-5 w-5" />
            )}
          </span>
        </button>
      ) : (
        <p className="text-heading-xlarge text-gray-70">{content}</p>
      )}
    </>
  );
};

export default CollapsibleQuestionText;
