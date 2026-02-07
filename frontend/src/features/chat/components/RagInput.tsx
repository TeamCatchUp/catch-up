'use client';

import { useState, useRef } from 'react';
import clsx from 'clsx';
import type { UseRagFiltersReturn } from '@/features/chat/hooks/useRagFilters';

import { GithubExplorer } from '@/shared/components/query/explorer/GithubExplorer';
import { JiraExplorer } from '@/shared/components/query/explorer/JiraExplorer';
import { SelectedFilterChips } from '@/shared/components/query/filter/SelectedFilterChips';
import { SearchOptionButton, SearchOptionDisabledButton } from '@/shared/components/SearchOptionButton';
import { FilterDropdown } from '@/shared/components/query/filter/FilterDropdown';
import { FilterOptionList } from '@/shared/components/query/filter/FilterOptionList';
import { PERSON_OPTIONS } from '@/shared/mocks/search/filterOptions';
import ToolTip from '@/shared/components/ui/ToolTip';

import Add from '/public/icons/icon/add_small.svg';
import ArrowSend from '/public/icons/icon/arrow_send.svg';
import Stop from '/public/icons/icon/stop.svg';
import Filter from '/public/icons/icon/filter-2.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconDivider from '@/public/icons/icon/divider.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconLock from '@/public/icons/icon/lock_filled.svg';
import IconFile from '@/public/icons/icon/file_filled.svg';
import IconFolder from '@/public/icons/icon/folder_blue.svg';
import IconJiraTicket from '@/public/icons/jira/Task.svg';
import IconJiraSprint from '@/public/icons/jira/Epic.svg';

interface RagInputProps {
  filters: UseRagFiltersReturn;
  isLoading: boolean;
  onSendMessage: (message: string) => Promise<void>;
  onStop: () => void;
  qaPairsLength: number;
  goToNewPage: (index: number) => void;
}

const RagInput = ({
  filters,
  isLoading,
  onSendMessage,
  onStop,
  qaPairsLength,
  goToNewPage,
}: RagInputProps) => {
  const [newInput, setNewInput] = useState('');
  const [isMultiLine, setIsMultiLine] = useState(false);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewInput(e.target.value);

    e.target.style.height = 'auto';
    const newHeight = Math.min(e.target.scrollHeight, 156);
    e.target.style.height = newHeight + 'px';

    setIsMultiLine(e.target.scrollHeight > 26);
  };

  const handleSendMessage = async () => {
    if (!newInput.trim() || isLoading) return;

    const message = newInput;
    setNewInput('');
    setIsMultiLine(false);

    if (textAreaRef.current) {
      textAreaRef.current.style.height = '26px';
    }

    goToNewPage(qaPairsLength);
    await onSendMessage(message);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const allSelectedChips = [
    ...filters.selectedPeople.map((name) => ({
      id: name,
      name,
      Icon: IconPerson,
      onRemove: () => filters.togglePerson(name),
    })),
    ...filters.selectedGithubItems
      .filter((item) => {
        const isParentSelected = filters.selectedGithubItems.some((potentialParent) => {
          if (potentialParent.id === item.id) return false;
          return potentialParent.children?.some((child: any) => child.id === item.id);
        });
        return !isParentSelected;
      })
      .map((item) => ({
        id: item.id,
        name: item.name,
        Icon: item.type === 'repo' ? IconGithub : item.type === 'tree' ? IconFolder : IconFile,
        onRemove: () => filters.toggleGithubItem(item),
      })),
    ...filters.selectedJiraItems
      .filter((item) => {
        const isParentSelected = filters.selectedJiraItems.some((potentialParent) => {
          if (potentialParent.id === item.id) return false;
          return potentialParent.children?.some((child: any) => child.id === item.id);
        });
        return !isParentSelected;
      })
      .map((item) => ({
        id: item.id,
        name: item.name,
        Icon: item.type === 'project' ? IconJira : item.type === 'board' ? IconJiraSprint : IconJiraTicket,
        onRemove: () => filters.toggleJiraItem(item),
      })),
  ];

  return (
    <div className="w-full flex-none bg-white px-24 pt-4 pb-8">
      <div className="mx-auto w-193.25">
        {/* Explorer Panel */}
        <div
          className={clsx(
            'border-neutral-2 mb-3 w-160 overflow-hidden rounded-2xl border bg-transparent',
            filters.activeExplorer ? 'shadow-dropdown-menu h-95 opacity-100' : 'max-h-0 border-none opacity-0',
          )}
        >
          <div className="h-80 overflow-y-auto p-4">
            <SelectedFilterChips chips={allSelectedChips} onReset={filters.handleResetAll} />
            {filters.activeExplorer === 'github' ? (
              <GithubExplorer
                selectedItems={filters.selectedGithubItems.map((i) => i.id)}
                onToggleItem={filters.toggleGithubItem}
                currentRepo={filters.currentRepo}
                onNavigate={filters.setCurrentRepo}
                onClickBack={filters.handleGithubClick}
              />
            ) : filters.activeExplorer === 'jira' ? (
              <JiraExplorer
                selectedItems={filters.selectedJiraItems.map((i) => i.id)}
                onToggleItem={filters.toggleJiraItem}
                currentProject={filters.currentJiraProject}
                onNavigate={filters.setCurrentJiraProject}
                onClickBack={filters.handleJiraClick}
              />
            ) : null}
          </div>
        </div>

        {/* Filter Bar */}
        <div
          className={clsx(
            'overflow-hidden transition-all duration-300 ease-in-out',
            filters.isFilterOpen ? 'mb-3 max-h-40 opacity-100' : 'mb-0 max-h-0 opacity-0',
          )}
        >
          <div className="no-scrollbar flex items-center gap-1.5 overflow-x-auto rounded-2xl p-2 whitespace-nowrap">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 self-stretch overflow-x-scroll px-1.5 whitespace-nowrap">
                <div className="flex items-center gap-2">
                  <SearchOptionButton
                    Icon={IconJira}
                    label={filters.jiraLabel}
                    selected={filters.selectedJiraItems.length > 0}
                    onClick={filters.handleJiraClick}
                  />
                  <SearchOptionButton
                    Icon={IconGithub}
                    label={filters.gitLabel}
                    selected={filters.selectedGithubItems.length > 0}
                    onClick={filters.handleGithubClick}
                  />
                  <SearchOptionDisabledButton Icon={IconLock} label="Wiki" />
                  <SearchOptionDisabledButton Icon={IconLock} label="Slack" />
                </div>
                <IconDivider className="text-gray-5 h-6 w-6 shrink-0" />

                <div className="flex items-center gap-2">
                  <FilterDropdown
                    open={filters.openPopover === 'person'}
                    onOpenChange={(o) => filters.setOpenPopover(o ? 'person' : null)}
                    trigger={
                      <SearchOptionButton
                        Icon={IconPerson}
                        label={filters.personLabel}
                        selected={filters.selectedPeople.length > 0}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => filters.setOpenPopover('person')}
                      />
                    }
                  >
                    <FilterOptionList
                      title="담당자 선택"
                      options={PERSON_OPTIONS}
                      selected={filters.selectedPeople}
                      onToggle={filters.togglePerson}
                      Icon={IconPerson}
                    />
                  </FilterDropdown>
                  <SearchOptionButton Icon={IconTag} label="부서" onMouseDown={(e) => e.preventDefault()} />
                  <SearchOptionButton Icon={IconSpace} label="프로젝트" onMouseDown={(e) => e.preventDefault()} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Input Bar */}
        <div
          className={clsx(
            'border-neutral-4 shadow-rag-bar flex gap-2 border bg-white px-3 py-2.5',
            isMultiLine ? 'items-end rounded-3xl' : 'items-center rounded-full',
          )}
        >
          <div className="group relative flex-shrink-0">
            <button className="icon-button-only-gray cursor-pointer rounded-full! p-1.5">
              <Add className="text-gray-70 h-7 w-7" />
            </button>
            <div className="relative top-0.5 right-10">
              <ToolTip text={'파일 추가 및 기타'} />
            </div>
          </div>

          <textarea
            ref={textAreaRef}
            placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
            value={newInput}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            className="text-body-medium placeholder:text-gray-30 flex-1 resize-none overflow-y-auto pr-2.5 outline-none"
            style={{ height: '26px', maxHeight: '156px' }}
          />

          <div className="flex flex-shrink-0 items-center gap-3">
            {!newInput.trim() && !isLoading && (
              <div
                onClick={filters.toggleFilter}
                className={clsx(
                  'box-button-outline-gray flex h-7 cursor-pointer items-center justify-center gap-1 px-1.5 py-1',
                  filters.isFilterOpen && 'bg-blue-5 border-blue-20',
                )}
              >
                <Filter className="relative top-0.5 h-4.5 w-4.5" />
                <span className="text-body-xsmall text-gray-50">필터</span>
              </div>
            )}

            {isLoading ? (
              <button
                onClick={onStop}
                className="bg-neutral-3 flex h-10 w-10 items-center justify-center rounded-full"
              >
                <Stop className="text-gray-70 relative left-px h-6 w-6 cursor-pointer" />
              </button>
            ) : (
              <button
                onClick={handleSendMessage}
                disabled={isLoading || !newInput.trim()}
                className={clsx(
                  'cursor-pointer rounded-full p-2 transition-colors',
                  newInput.trim() ? 'bg-blue-50' : 'bg-neutral-1 border-neutral-2 border',
                )}
              >
                <ArrowSend
                  className={clsx('h-6 w-6 cursor-pointer', newInput.trim() ? 'brightness-0 invert' : 'text-gray-30')}
                />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RagInput;
