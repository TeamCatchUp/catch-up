'use client';

import { useRef, useState } from 'react';
import { useUserStore } from '@/store/userStore';
import { useSearchFilters } from '@/hooks/search/useSearchFilters';
import { useSearchInput } from '@/hooks/search/useSearchInput';
import { useEscapeKey } from '@/hooks/shared/useEscapeKey';
import { useOutsideClick } from '@/hooks/shared/useOutsideClick';

import TopNavbar from '@/components/shared/topNavbar/TopNavbar';
import HowToUse from '@/components/home/cardComponents/HowToUse';
import LinkTool from '@/components/home/cardComponents/LinkTool';
import TaskRecentlyChecked from '@/components/home/cardComponents/TaskRecentlyChecked';
import TaskRecentlyCheckedModal from '@/components/home/modal/TaskRecentlyCheckedModal';
import QueryInput from '@/components/shared/queryBox/QueryInput';
import FilterBar from '@/components/shared/queryBox/FilterBar';
import ExplorerPanel from '@/components/shared/queryBox/ExplorerPanel';
import { SelectedFilterChips } from '@/components/search/filter/SelectedFilterChips';

export default function Home() {
  const user = useUserStore((state) => state.user);
  const [selectedTask, setSelectedTask] = useState<TaskRecentlyCheckedCard | null>(null);
  const [isClosing, setIsClosing] = useState(false);

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

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      setSelectedTask(null);
      setIsClosing(false);
    }, 200);
  };

  return (
    <div className="bg-home-gradient flex flex-col">
      <TopNavbar pageType="home" />

      {/* Query Section */}
      <div className="flex flex-col items-center gap-4 self-stretch pt-18 pb-18">
        {/* Hero */}
        <div className="flex h-24 flex-col items-center justify-center gap-3 text-gray-50">
          <h1 className="text-display-xlarge text-normal-normal">반갑습니다, {user?.name ?? ''}님!</h1>
          <p className="text-heading-large text-normal-alternative">
            무엇을 도와드릴까요? 필요한 업무정보를 찾아보세요.
          </p>
        </div>

        {/* Query Box */}
        <div
          ref={containerRef}
          className={`shadow-rag-bar border-neutral-4 flex w-190 flex-col items-center gap-1.5 border border-solid bg-white ${input.isFocused ? 'h-125.5 max-h-135 min-h-92.5 overflow-hidden rounded-[28px] p-3' : 'rounded-rounded h-auto p-3'
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

      <div className="flex flex-col items-center gap-16 px-16 pt-10 pb-30">
        {/* <TaskRecentlyChecked onClickCard={setSelectedTask} /> */}
        <HowToUse />
        <LinkTool />
      </div>

      {selectedTask && (
        <div
          className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-200 ${isClosing ? 'opacity-0' : 'opacity-100'
            }`}
        >
          <div onClick={handleClose} className="absolute inset-0 bg-white/50 transition-opacity duration-200" />
          <div
            className={`relative z-10 transition-all duration-200 ${isClosing ? 'scale-95 opacity-0' : 'scale-100 opacity-100'
              }`}
          >
            <TaskRecentlyCheckedModal task={selectedTask} onClose={handleClose} />
          </div>
        </div>
      )}
    </div>
  );
}
