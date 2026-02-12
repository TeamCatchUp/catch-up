'use client';

import { useRef, useState } from 'react';

import HowToUse from '@/features/home/components/HowToUse';
import QuestionTips from '@/features/home/components/QuestionTips';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import QueryBox from '@/shared/components/query/QueryBox';
import { useQuestionHistoryGate } from '@/shared/hooks/query/useQuestionHistoryGate';
import { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import { useSearchInput } from '@/shared/hooks/query/useSearchInput';
import { useEscapeKey } from '@/shared/hooks/useEscapeKey';
import { useOutsideClick } from '@/shared/hooks/useOutsideClick';
import { useUserStore } from '@/shared/store/userStore';

export default function Home() {
  const user = useUserStore((state) => state.user);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const filters = useSearchFilters();
  const input = useSearchInput({ inputRef });
  const { shouldShowNoHistoryBox } = useQuestionHistoryGate();
  const [isNoHistoryExpanded, setIsNoHistoryExpanded] = useState(true);

  useEscapeKey(() => {
    input.setIsFocused(false);
    inputRef.current?.blur();
  });

  useOutsideClick(containerRef, () => {
    if (filters.openPopover) return;
    input.setIsFocused(false);
    inputRef.current?.blur();
    if (shouldShowNoHistoryBox) {
      setIsNoHistoryExpanded(false);
    }
  });

  return (
    <div className="bg-home-gradient flex flex-col">
      <TopNavbar pageType="home" />

      {/* Query Section */}
      <div className="flex flex-col items-center gap-4 self-stretch pt-18 pb-18">
        {/* TEXT */}
        <div className="grid h-24 place-items-center">
          <div
            className={`[grid-area:1/1] flex flex-col items-center gap-3 transition-opacity duration-300 ${
              input.isFocused ? 'pointer-events-none opacity-0' : 'opacity-100'
            }`}
          >
            <h1 className="text-display-xlarge text-normal-normal">반갑습니다, {user?.name ?? ''}님!</h1>
            <p className="text-heading-large text-normal-alternative">
              무엇을 도와드릴까요? 필요한 업무정보를 찾아보세요.
            </p>
          </div>
          <div
            className={`[grid-area:1/1] flex flex-col items-center text-center transition-opacity duration-300 ${
              input.isFocused ? 'opacity-100' : 'pointer-events-none opacity-0'
            }`}
          >
            <h1 className="text-display-xlarge text-normal-normal">
              사내 AI 탐색으로
              <br />
              <span className="text-blue-50">필요한 업무 자료를 </span>
              바로 찾아보세요
            </h1>
          </div>
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
        <HowToUse />
      </div>
    </div>
  );
}
