'use client';

// HomeContent의 ai 모드 콘텐츠 — HeroText(ai) + QueryBox + PromptChips + 하단 tips/howto.
// 외부 컨테이너 padding/gap은 원본 HomeContent의 py-18 gap-6에서 분리해 위/아래로 흘림.

import type { RefObject } from 'react';

import QueryBox from '@/shared/components/query/QueryBox';
import type { useSearchFilters } from '@/shared/hooks/query/useSearchFilters';
import type { useSearchInput } from '@/shared/hooks/query/useSearchInput';

import { tipData } from '../constants/questionTips';
import HeroText from './HeroText';
import HowToUse from './HowToUse';
import PromptChips from './PromptChips';
import QuestionTips from './QuestionTips';

interface HomeAiSectionProps {
  input: ReturnType<typeof useSearchInput>;
  filters: ReturnType<typeof useSearchFilters>;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  containerRef: RefObject<HTMLDivElement | null>;
  shouldShowNoHistoryBox: boolean;
  isNoHistoryExpanded: boolean;
}

export default function HomeAiSection({
  input,
  filters,
  inputRef,
  containerRef,
  shouldShowNoHistoryBox,
  isNoHistoryExpanded,
}: HomeAiSectionProps) {
  return (
    <>
      <div className="flex flex-col items-center gap-6 pb-18">
        <div className="grid h-24 place-items-center">
          <HeroText mode="ai" isFocused={input.isFocused} />
        </div>
        <div ref={containerRef} className="flex flex-col items-center gap-4">
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
      <div
        className={`flex flex-col items-center gap-16 px-16 pt-4 pb-30 transition-[opacity,transform] duration-300 ${
          input.isFocused ? 'pointer-events-none h-0 translate-y-4 overflow-hidden opacity-0' : 'opacity-100'
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
        <HowToUse />
      </div>
    </>
  );
}
