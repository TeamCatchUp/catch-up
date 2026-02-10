'use client';

import { useRef } from 'react';

import HowToUse from '@/features/home/components/HowToUse';
import LinkTool from '@/features/home/components/LinkTool';
import TopNavbar from '@/shared/components/layout/topNavbar/TopNavbar';
import ExplorerPanel from '@/shared/components/query/ExplorerPanel';
import { SelectedFilterChips } from '@/shared/components/query/filter/SelectedFilterChips';
import FilterBar from '@/shared/components/query/FilterBar';
import QueryInput from '@/shared/components/query/QueryInput';
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
        <div
          ref={containerRef}
          className={`shadow-rag-bar border-neutral-4 flex w-190 flex-col items-center gap-1.5 border border-solid bg-white ${input.isFocused ? 'h-125.5 max-h-135 min-h-92.5 overflow-hidden rounded-[28px] p-3' : 'rounded-rounded h-auto p-3'
            }`}
        >
          <QueryInput input={input} inputRef={inputRef} />

          {input.isFocused && (
            <div className="animate-in fade-in-0 slide-in-from-top-3 duration-300 border-neutral-4 mt-1 flex min-h-0 w-full flex-1 flex-col gap-0 overflow-hidden border-t pt-2">
              <FilterBar filters={filters} inputRef={inputRef} />
              <SelectedFilterChips chips={filters.allSelectedChips} onReset={filters.handleResetAll} />
              <ExplorerPanel />
            </div>
          )}
        </div>
      </div>

      <div
        className={`flex flex-col items-center gap-16 px-16 pt-10 pb-30 transition-all duration-300 ${
          input.isFocused ? 'pointer-events-none translate-y-4 opacity-0' : 'opacity-100'
        }`}
      >
        <HowToUse />
        <LinkTool />
      </div>
    </div>
  );
}
