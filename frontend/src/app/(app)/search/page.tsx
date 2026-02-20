'use client';

import { useRef, useState } from 'react';

import QuestionTips from '@/features/home/components/QuestionTips';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import QueryBox from '@/shared/components/query/QueryBox';
import { useQuestionHistoryGate } from '@/shared/hooks/query/useQuestionHistoryGate';
import { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import { useSearchInput } from '@/shared/hooks/query/useSearchInput';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';

export default function Search() {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const filters = useSearchFilters();
  const input = useSearchInput({ inputRef });
  const { shouldShowNoHistoryBox } = useQuestionHistoryGate();
  const [isNoHistoryExpanded, setIsNoHistoryExpanded] = useState(true);

  // QueryBox 포커스 해제 + no-history 패널 닫기 공통 로직
  const handleClose = () => {
    input.setIsFocused(false);
    inputRef.current?.blur();
    if (shouldShowNoHistoryBox) {
      setIsNoHistoryExpanded(false);
    }
  };

  useEscapeKey(handleClose);

  useOutsideClick(containerRef, () => {
    if (filters.openPopover) return;
    handleClose();
  });

  return (
    <div className={`bg-home-gradient flex flex-col ${input.isFocused ? 'h-full overflow-hidden' : ''}`}>
      <TopNavbar pageType="search" />

      {/* Query Section */}
      <div className="flex flex-col items-center gap-4 self-stretch pt-18 pb-18">
        {/* Hero */}
        <div className="flex h-24 flex-col items-center justify-center gap-3 text-gray-50">
          <h1 className="text-display-xlarge text-normal-normal">찾지 말고, 물어보세요.</h1>
          <p className="text-heading-large text-normal-alternative">
            Jira, GitHub, Wiki... 흩어진 정보를 모아 한 번에 알려드려요.
          </p>
        </div>

        {/* Query Box */}
        <QueryBox
          containerRef={containerRef}
          inputRef={inputRef}
          input={input}
          filters={filters}
          variant={shouldShowNoHistoryBox ? 'no-history' : 'default'}
          noHistoryExpanded={isNoHistoryExpanded || input.isFocused}
        />
      </div>

      {/* Tips Section */}
      <div
        className={`flex flex-col items-center gap-16 px-16 pt-10 pb-30 transition-all duration-300 ${
          input.isFocused ? 'pointer-events-none translate-y-4 opacity-0' : 'opacity-100'
        }`}
      >
        <QuestionTips
          onTipClick={(query) => {
            input.setValue(query);
            input.setIsFocused(true);
            inputRef.current?.focus();
          }}
        />
      </div>
    </div>
  );
}
