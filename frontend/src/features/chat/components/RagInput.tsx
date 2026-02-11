'use client';

import { useRef, useState } from 'react';

import type { UseRagFiltersReturn } from '@/features/chat/hooks/useRagFilters';
import IconDivider from '@/public/icons/icon/divider.svg';
import IconLock from '@/public/icons/icon/lock_filled.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSlack from '@/public/icons/logo/Slack.svg';
import { FilterDropdown } from '@/shared/components/query/filter/FilterDropdown';
import { FilterOptionList } from '@/shared/components/query/filter/FilterOptionList';
import { SearchOptionButton, SearchOptionDisabledButton } from '@/shared/components/SearchOptionButton';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { DEPARTMENT_OPTIONS, PERSON_OPTIONS, PROJECT_OPTIONS } from '@/shared/mocks/search/filterOptions';
import { cn } from '@/shared/utils/cn';

import Add from '/public/icons/icon/add_small.svg';
import ArrowSend from '/public/icons/icon/arrow_send.svg';
import Filter from '/public/icons/icon/filter-2.svg';
import Stop from '/public/icons/icon/stop.svg';

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

  return (
    <div className="w-full flex-none bg-white px-24 pt-4 pb-8">
      <div className="mx-auto w-193.25">
        {/* Filter Bar */}
        <div
          className={cn(
            'overflow-hidden transition-all duration-300 ease-in-out',
            filters.isFilterOpen ? 'mb-3 max-h-40 opacity-100' : 'mb-0 max-h-0 opacity-0',
          )}
        >
          <div className="no-scrollbar flex items-center gap-1.5 overflow-x-auto rounded-2xl p-2 whitespace-nowrap">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 self-stretch overflow-x-scroll px-1.5 whitespace-nowrap">
                <div className="flex items-center gap-2">
                  <SearchOptionButton Icon={IconJira} label="Jira" selected={filters.selectedSources.includes('jira')} onClick={() => filters.toggleSource('jira')} />
                  <SearchOptionButton Icon={IconGithub} label="Github" selected={filters.selectedSources.includes('github')} onClick={() => filters.toggleSource('github')} />
                  <SearchOptionButton Icon={IconSlack} label="Slack" selected={filters.selectedSources.includes('slack')} onClick={() => filters.toggleSource('slack')} />
                  <SearchOptionDisabledButton Icon={IconLock} label="Wiki" />
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
                  <FilterDropdown
                    open={filters.openPopover === 'department'}
                    onOpenChange={(o) => filters.setOpenPopover(o ? 'department' : null)}
                    trigger={
                      <SearchOptionButton
                        Icon={IconTag}
                        label={filters.deptLabel}
                        selected={filters.selectedDepts.length > 0}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => filters.setOpenPopover('department')}
                      />
                    }
                  >
                    <FilterOptionList
                      title="부서 선택"
                      options={DEPARTMENT_OPTIONS}
                      selected={filters.selectedDepts}
                      onToggle={filters.toggleDept}
                      Icon={IconTag}
                    />
                  </FilterDropdown>
                  <FilterDropdown
                    open={filters.openPopover === 'project'}
                    onOpenChange={(o) => filters.setOpenPopover(o ? 'project' : null)}
                    trigger={
                      <SearchOptionButton
                        Icon={IconSpace}
                        label={filters.projectLabel}
                        selected={filters.selectedProjects.length > 0}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => filters.setOpenPopover('project')}
                      />
                    }
                  >
                    <FilterOptionList
                      title="프로젝트 선택"
                      options={PROJECT_OPTIONS}
                      selected={filters.selectedProjects}
                      onToggle={filters.toggleProject}
                      Icon={IconSpace}
                    />
                  </FilterDropdown>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Input Bar */}
        <div
          className={cn(
            'border-neutral-4 shadow-rag-bar flex gap-2 border bg-white px-3 py-2.5',
            isMultiLine ? 'items-end rounded-3xl' : 'items-center rounded-full',
          )}
        >
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="icon-button-only-gray shrink-0 cursor-pointer rounded-full! p-1.5">
                <Add className="text-gray-70 h-7 w-7" />
              </button>
            </TooltipTrigger>
            <TooltipContent>파일 추가 및 기타</TooltipContent>
          </Tooltip>

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

          <div className="flex shrink-0 items-center gap-3">
            {!newInput.trim() && !isLoading && (
              <div
                onClick={filters.toggleFilter}
                className={cn(
                  'box-button-outline-gray flex h-7 cursor-pointer items-center justify-center gap-1 px-1.5 py-1',
                  filters.isFilterOpen && 'bg-blue-5 border-blue-20',
                )}
              >
                <Filter className="h-4.5 w-4.5" />
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
                className={cn(
                  'cursor-pointer rounded-full p-2 transition-colors',
                  newInput.trim() ? 'bg-blue-50' : 'bg-neutral-1 border-neutral-2 border',
                )}
              >
                <ArrowSend
                  className={cn('h-6 w-6 cursor-pointer', newInput.trim() ? 'brightness-0 invert' : 'text-gray-30')}
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
