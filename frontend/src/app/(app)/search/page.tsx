'use client';

import { useRef, useState } from 'react';

import PromptChips from '@/features/home/components/PromptChips';
import QuestionTips from '@/features/home/components/QuestionTips';
import { tipData } from '@/features/home/constants/questionTips';
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
  const input = useSearchInput({ inputRef, tipData });
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
    <div className={`bg-home-gradient flex min-h-full flex-col ${input.isFocused ? 'h-full overflow-y-auto' : ''}`}>
      <TopNavbar pageType="search" />

      {/* Query Section */}
      <div className="flex flex-col items-center gap-4 self-stretch pt-18 pb-18">
        {/* Hero */}
        <div className="flex h-24 flex-col items-center justify-center gap-3 text-content-alternative">
          <h1 className="text-display-xlarge text-content-normal">찾지 말고, 물어보세요.</h1>
          <p className="text-heading-large text-content-alternative">
            Jira, GitHub, Wiki... 흩어진 정보를 모아 한 번에 알려드려요.
          </p>
        </div>

        {/* Query Box + Prompt Chips wrapper (useOutsideClick 영역) */}
        <div ref={containerRef} className="flex flex-col items-center gap-8">
          <QueryBox
            inputRef={inputRef}
            input={input}
            filters={filters}
            variant={shouldShowNoHistoryBox ? 'no-history' : 'default'}
            noHistoryExpanded={isNoHistoryExpanded || input.isFocused}
            tipData={tipData}
          />

          {input.isFocused && (
            <PromptChips
              selectedIndex={input.selectedTipIndex}
              onChipClick={(index) => {
                input.resetTemplateFields();
                input.setIsFromTemplate(true);
                input.setSelectedTipIndex(index);
              }}
            />
          )}
        </div>
      </div>

      {/* Tips Section */}
      <div
        className={`flex flex-col items-center gap-16 px-16 pt-10 pb-30 transition-all duration-300 ${
          input.isFocused ? 'pointer-events-none translate-y-4 opacity-0' : 'opacity-100'
        }`}
      >
        <QuestionTips
          onTipClick={(index) => {
            input.resetTemplateFields();
            input.setIsFromTemplate(true);
            input.setSelectedTipIndex(index);
            input.setIsFocused(true);
          }}
        />
      </div>
    </div>
  );
}
