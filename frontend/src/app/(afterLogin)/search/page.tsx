'use client';

import { useRef } from 'react';
import { usePathname } from 'next/navigation';
import { useUserStore } from '@/store/userStore';
import { useSearchFilters } from '@/hooks/search/useSearchFilters';
import { useSearchInput } from '@/hooks/search/useSearchInput';
import { useEscapeKey } from '@/hooks/shared/useEscapeKey';
import { useOutsideClick } from '@/hooks/shared/useOutsideClick';

// Icons
import IconAdd from '@/public/icons/icon/add_small.svg';
import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconDivider from '@/public/icons/icon/divider.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconLock from '@/public/icons/icon/lock_filled.svg';

// Components
import { SearchOptionButton, SearchOptionDisabledButton } from '@/components/UI/SearchOptionButton';
import { SearchOptionPopover } from '@/components/search/SearchOptionPopover';
import { OptionListPopover } from '@/components/search/OptionListPopover';
import { GithubExplorer } from '@/components/search/GithubExplorer';
import { JiraExplorer } from '@/components/search/JiraExplorer';
import { DefaultSearchContent } from '@/components/search/DefaultSearchContent';
import { SelectedFilterChips } from '@/components/search/SelectedFilterChips';
import { PERSON_OPTIONS } from '@/components/search/OptionDummyData';

export default function Search() {
  const pathname = usePathname();
  const user = useUserStore((state) => state.user);

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

  const isSearchPage = pathname === '/search';

  return (
    <div className="flex flex-col items-center gap-4 self-stretch pt-18 pb-18">
      {/* Hero Section */}
      {isSearchPage ? (
        <div className="flex h-24 flex-col items-center justify-center gap-3 text-gray-50">
          <div className="text-display-xlarge text-normal-normal">찾지 말고, 물어보세요.</div>
          <div className="text-heading-large text-normal-alternative">
            Jira, GitHub, Wiki... 흩어진 정보를 모아 한 번에 알려드려요.
          </div>
        </div>
      ) : (
        <div className="flex h-24 flex-col items-center justify-center gap-3 text-gray-50">
          <div className="text-display-xlarge text-normal-normal">반갑습니다, {user?.name}님!</div>
          <div className="text-heading-large text-normal-alternative">
            무엇을 도와드릴까요? 필요한 업무정보를 찾아보세요.
          </div>
        </div>
      )}

      {/* Search Container */}
      <div
        ref={containerRef}
        className={`shadow-rag-bar border-neutral-4 flex w-190 flex-col items-center gap-1.5 border border-solid bg-white ${
          input.isFocused ? 'h-125.5 max-h-135 min-h-92.5 overflow-hidden rounded-[28px] p-3' : 'rounded-rounded h-auto p-3'
        }`}
      >
        {/* Input Row */}
        <div className="flex w-full items-end justify-between">
          <div className="text-button-secondary-mono relative bottom-0.5 mr-2 flex h-10 w-10 cursor-pointer items-center justify-center p-1.5">
            <IconAdd className="text-gray-70 h-7 w-7" />
          </div>
          <div className="flex flex-1 items-center gap-2">
            <textarea
              ref={inputRef}
              rows={1}
              className="text-body-medium mb-2.25 w-full resize-none outline-none"
              placeholder="업무와 관련해 궁금한 무엇이든 물어보세요!"
              value={input.value}
              onFocus={() => input.setIsFocused(true)}
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
            className={`rounded-rounded relative bottom-px ml-2 flex items-center border border-solid p-2 ${
              input.hasText ? 'cursor-pointer border-blue-50 bg-blue-50' : 'bg-neutral-1 border-neutral-2'
            }`}
          >
            <IconArrowSend className={`${input.hasText ? 'brightness-0 invert' : 'text-gray-30'} h-6 w-6`} />
          </button>
        </div>

        {/* Expanded Content */}
        {input.isFocused && (
          <div className="border-neutral-4 mt-1 flex min-h-0 w-full flex-1 flex-col gap-0 overflow-hidden border-t pt-2">
            {/* Filter Options */}
            <div className="flex items-center gap-1.5 self-stretch overflow-x-scroll px-1.5 whitespace-nowrap">
              <div className="flex items-center gap-2">
                <SearchOptionButton
                  Icon={IconJira}
                  label={filters.labels.jira}
                  selected={filters.selectedJiraItems.length > 0}
                  onClick={filters.handleJiraClick}
                />
                <SearchOptionButton
                  Icon={IconGithub}
                  label={filters.labels.git}
                  selected={filters.selectedGithubItems.length > 0}
                  onClick={filters.handleGithubClick}
                />
                <SearchOptionDisabledButton Icon={IconLock} label="Wiki" />
                <SearchOptionDisabledButton Icon={IconLock} label="Slack" />
              </div>
              <IconDivider className="text-gray-5 h-6 w-6 shrink-0" />
              <div className="flex items-center gap-2">
                <SearchOptionPopover
                  open={filters.openPopover === 'person'}
                  onOpenChange={(o) => {
                    filters.setOpenPopover(o ? 'person' : null);
                    if (!o) inputRef.current?.focus();
                  }}
                  trigger={
                    <SearchOptionButton
                      Icon={IconPerson}
                      label={filters.labels.person}
                      selected={filters.selectedPeople.length > 0}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => filters.setOpenPopover('person')}
                    />
                  }
                >
                  <OptionListPopover
                    title="담당자 선택"
                    options={PERSON_OPTIONS}
                    selected={filters.selectedPeople}
                    onToggle={filters.togglePerson}
                    Icon={IconPerson}
                  />
                </SearchOptionPopover>
                <SearchOptionButton
                  Icon={IconTag}
                  label={filters.labels.dept}
                  selected={filters.selectedDepts.length > 0}
                  onMouseDown={(e) => e.preventDefault()}
                />
                <SearchOptionButton
                  Icon={IconSpace}
                  label={filters.labels.project}
                  selected={filters.selectedProjects.length > 0}
                  onMouseDown={(e) => e.preventDefault()}
                />
              </div>
            </div>

            {/* Selected Chips */}
            <SelectedFilterChips chips={filters.allSelectedChips} onReset={filters.handleResetAll} />

            {/* Explorer Content */}
            <div className="no-scrollbar flex min-h-0 flex-1 flex-col items-start gap-2 self-stretch overflow-y-auto pt-2">
              {filters.explorerMode === 'github' ? (
                <GithubExplorer
                  selectedItems={filters.selectedGithubItems.map((i) => i.id)}
                  onToggleItem={filters.toggleGithubItem}
                  currentRepo={filters.currentRepo}
                  onNavigate={filters.setCurrentRepo}
                  onClickBack={filters.handleGithubClick}
                />
              ) : filters.explorerMode === 'jira' ? (
                <JiraExplorer
                  selectedItems={filters.selectedJiraItems.map((i) => i.id)}
                  onToggleItem={filters.toggleJiraItem}
                  currentProject={filters.currentJiraProject}
                  onNavigate={filters.setCurrentJiraProject}
                  onClickBack={filters.handleJiraClick}
                />
              ) : (
                <DefaultSearchContent />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
