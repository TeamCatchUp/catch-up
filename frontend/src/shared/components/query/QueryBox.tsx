/**
 * QueryBox
 * Home/Search 공통 질의 입력 영역.
 * - default: 포커스 시 FilterBar + ExplorerPanel 노출
 * - no-history: 질문 이력 없는 사용자용 온보딩 패널 (외부 클릭으로 접기 가능)
 */

import { RefObject } from 'react';

import SourceChipsRow from '@/shared/components/SourceChipsRow';
import type { UseSearchFiltersReturn } from '@/shared/hooks/query/useSearchFilters';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';
import type { TipData } from '@/shared/types/template';
import { cn } from '@/shared/utils/cn';

import ExplorerPanel from './ExplorerPanel';
import QueryInput from './QueryInput';

interface QueryBoxProps {
  containerRef?: RefObject<HTMLDivElement | null>;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  input: UseSearchInputReturn;
  filters: UseSearchFiltersReturn;
  variant?: 'default' | 'no-history';
  noHistoryExpanded?: boolean;
  highlightBracketPlaceholders?: boolean;
  tipData?: TipData[];
}

const QueryBox = ({
  containerRef,
  inputRef,
  input,
  filters,
  variant = 'default',
  noHistoryExpanded = true,
  tipData,
}: QueryBoxProps) => {
  const isNoHistory = variant === 'no-history';
  const showPanel = isNoHistory ? noHistoryExpanded : input.isFocused;

  const maxH = input.isFromTemplate ? 'max-h-160' : 'max-h-135';

  const containerClassName =
    isNoHistory && noHistoryExpanded
      ? `gap-3 min-h-92.5 ${maxH} overflow-hidden rounded-[30px] px-4 py-3`
      : !isNoHistory && input.isFocused
        ? `gap-1.5 min-h-92.5 ${maxH} overflow-hidden rounded-[30px] px-4 py-3`
        : `gap-1.5 h-auto px-4 py-3 ${input.isMultiLine ? 'rounded-[30px]' : 'rounded-rounded'}`;

  const handleExampleClick = (query: string) => {
    input.setValue(query);
    input.setIsFocused(true);
    inputRef.current?.focus();
  };

  return (
    <div
      ref={containerRef}
      className={`shadow-rag-bar border-line-normal-normal bg-fill-normal-normal flex w-190 flex-col items-center border border-solid ${containerClassName}`}
    >
      <QueryInput input={input} inputRef={inputRef} tipData={tipData} />

      {showPanel && (
        <div
          className={cn(
            'animate-in fade-in-0 border-line-normal-normal flex min-h-0 w-full flex-1 flex-col gap-3 overflow-hidden border-t pt-3 duration-300',
            !isNoHistory && 'slide-in-from-top-3 mt-1',
          )}
        >
          <SourceChipsRow
            selectedSources={filters.selectedSources}
            onToggle={filters.setSelectedSources}
            className="justify-start self-stretch overflow-x-scroll py-0.5 whitespace-nowrap"
          />
          <ExplorerPanel variant={variant} onExampleClick={handleExampleClick} />
        </div>
      )}
    </div>
  );
};

export default QueryBox;
