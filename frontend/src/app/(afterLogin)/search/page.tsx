'use client';

import { useRef } from 'react';
import { useSearchFilters } from '@/hooks/search/useSearchFilters';
import { useSearchInput } from '@/hooks/search/useSearchInput';
import { useEscapeKey } from '@/hooks/shared/useEscapeKey';
import { useOutsideClick } from '@/hooks/shared/useOutsideClick';

import QueryInput from '@/components/shared/queryBox/QueryInput';
import FilterBar from '@/components/shared/queryBox/FilterBar';
import ExplorerPanel from '@/components/shared/queryBox/ExplorerPanel';
import { SelectedFilterChips } from '@/components/search/SelectedFilterChips';

export default function Search() {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const filters = useSearchFilters();
  const input = useSearchInput({ currentRepo: filters.currentRepo, inputRef });

  useEscapeKey(() => {
    input.setIsFocused(false);
    inputRef.current?.blur();
  });

  useOutsideClick(containerRef, () => {
    if (input.hasText || filters.openPopover) return;
    input.setIsFocused(false);
    inputRef.current?.blur();
  });

  return (
    <div className="flex flex-col items-center gap-4 self-stretch pt-18 pb-18">
      {/* Hero */}
      <div className="flex h-24 flex-col items-center justify-center gap-3 text-gray-50">
        <h1 className="text-display-xlarge text-normal-normal">찾지 말고, 물어보세요.</h1>
        <p className="text-heading-large text-normal-alternative">
          Jira, GitHub, Wiki... 흩어진 정보를 모아 한 번에 알려드려요.
        </p>
      </div>

      {/* Query Box */}
      <div
        ref={containerRef}
        className={`shadow-rag-bar border-neutral-4 flex w-190 flex-col items-center gap-1.5 border border-solid bg-white ${
          input.isFocused ? 'h-125.5 max-h-135 min-h-92.5 overflow-hidden rounded-[28px] p-3' : 'rounded-rounded h-auto p-3'
        }`}
      >
        <QueryInput input={input} inputRef={inputRef} />

        {input.isFocused && (
          <div className="border-neutral-4 mt-1 flex min-h-0 w-full flex-1 flex-col gap-0 overflow-hidden border-t pt-2">
            <FilterBar filters={filters} inputRef={inputRef} />
            <SelectedFilterChips chips={filters.allSelectedChips} onReset={filters.handleResetAll} />
            <ExplorerPanel filters={filters} />
          </div>
        )}
      </div>
    </div>
  );
}
