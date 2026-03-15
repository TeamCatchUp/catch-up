'use client';

import { useRef, useState } from 'react';

import type { UseRagFiltersReturn } from '@/features/chat/hooks/filter/useRagFilters';
import ArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconDivider from '@/public/icons/icon/divider.svg';
import DropdownDown from '@/public/icons/icon/dropdown_down.svg';
import DropdownUp from '@/public/icons/icon/dropdown_up.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import Stop from '@/public/icons/icon/stop.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconConfluence from '@/public/icons/logo/Confluence.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSlack from '@/public/icons/logo/Slack.svg';
import { FilterDropdown } from '@/shared/components/query/filter/FilterDropdown';
import { FilterOptionList } from '@/shared/components/query/filter/FilterOptionList';
import { SearchOptionButton } from '@/shared/components/SearchOptionButton';
import { cn } from '@/shared/utils/cn';

interface RagInputProps {
  filters: UseRagFiltersReturn;
  isLoading: boolean;
  onSendMessage: (message: string) => Promise<void>;
  onStop: () => void;
  onNewMessage: () => void;
}

const RagInput = ({ filters, isLoading, onSendMessage, onStop, onNewMessage }: RagInputProps) => {
  const [newInput, setNewInput] = useState('');
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewInput(e.target.value);

    e.target.style.height = 'auto';
    const newHeight = Math.min(e.target.scrollHeight, 230);
    e.target.style.height = newHeight + 'px';
  };

  const handleSendMessage = async () => {
    if (!newInput.trim() || isLoading) return;

    const message = newInput;
    setNewInput('');

    if (textAreaRef.current) {
      textAreaRef.current.style.height = '26px';
    }

    onNewMessage();
    await onSendMessage(message);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="to-fill-normal bg-gradient-to-b from-transparent px-6 py-8 backdrop-blur-[10px] lg:px-24">
      <div className="shadow-rag-bar border-edge-normal bg-fill-normal mx-auto flex w-full max-w-[776px] flex-none flex-col rounded-3xl border px-3 py-4">
        {/* Filter Bar (카드 내부 상단) */}
        <div
          className={cn(
            'overflow-hidden transition-all duration-300 ease-in-out',
            filters.isFilterOpen ? 'mb-2.5 max-h-40 opacity-100' : 'max-h-0 opacity-0',
          )}
        >
          <div className="flex items-center gap-1.5">
            <button
              onClick={filters.toggleFilter}
              className="text-button-secondary-mono text-body-xsmall text-content-neutral shrink-0 cursor-pointer px-1.5 py-1"
            >
              접기
            </button>
            <div className="flex items-center gap-2.5">
              <SearchOptionButton
                Icon={IconJira}
                label="Jira"
                selected={filters.selectedSources.includes('jira')}
                onClick={() => filters.toggleSource('jira')}
              />
              <SearchOptionButton
                Icon={IconConfluence}
                label="Confluence"
                selected={filters.selectedSources.includes('confluence')}
                onClick={() => filters.toggleSource('confluence')}
              />
              <SearchOptionButton
                Icon={IconGithub}
                label="Github"
                selected={filters.selectedSources.includes('github')}
                onClick={() => filters.toggleSource('github')}
              />
              <SearchOptionButton
                Icon={IconSlack}
                label="Slack"
                selected={filters.selectedSources.includes('slack')}
                onClick={() => filters.toggleSource('slack')}
              />
            </div>
            <IconDivider className="text-edge-assistive h-6 w-6 shrink-0" />
            <div className="flex items-center gap-2.5">
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
                  options={[]}
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
                  options={[]}
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
                  options={[]}
                  selected={filters.selectedProjects}
                  onToggle={filters.toggleProject}
                  Icon={IconSpace}
                />
              </FilterDropdown>
            </div>
          </div>
        </div>

        {/* Textarea */}
        <div className="px-1">
          <textarea
            ref={textAreaRef}
            placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
            value={newInput}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            className="text-body-medium text-content-normal placeholder:text-content-assistive w-full resize-none overflow-y-auto outline-none"
            style={{ height: '26px', maxHeight: '230px' }}
          />
        </div>

        {/* 하단 컨트롤 바 */}
        <div className="mt-2.5 flex h-8 items-center justify-between">
          {/* 상세 검색 토글 */}
          <button
            onClick={filters.toggleFilter}
            className={cn(
              'flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1',
              filters.isFilterOpen && 'bg-fill-interaction-pressed',
            )}
          >
            <span className="text-body-small text-content-neutral">상세 검색</span>
            {filters.isFilterOpen ? (
              <DropdownUp className="text-icon-normal h-4.5 w-4.5" />
            ) : (
              <DropdownDown className="text-icon-normal h-4.5 w-4.5" />
            )}
          </button>

          {/* 전송 / 중지 버튼 */}
          {isLoading ? (
            <button
              onClick={onStop}
              className="bg-fill-interaction-pressed flex h-10 w-10 items-center justify-center rounded-full"
            >
              <Stop className="text-content-neutral relative left-px h-6 w-6 cursor-pointer" />
            </button>
          ) : (
            <button
              onClick={handleSendMessage}
              disabled={isLoading || !newInput.trim()}
              className={cn(
                'cursor-pointer rounded-full p-2 transition-colors',
                newInput.trim() ? 'bg-fill-primary' : 'bg-fill-strong border-edge-assistive border',
              )}
            >
              <ArrowSend
                className={cn(
                  'h-6 w-6 cursor-pointer',
                  newInput.trim() ? 'brightness-0 invert' : 'text-content-assistive',
                )}
              />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default RagInput;
