'use client';

import { useRef, useState } from 'react';

import type { UseRagFiltersReturn } from '@/features/chat/hooks/filter/useRagFilters';
import ArrowSend from '@/public/icons/icon/arrow_send.svg';
import CancelSmall from '@/public/icons/icon/cancel_small.svg';
import SearchFile from '@/public/icons/icon/search_file.svg';
import Stop from '@/public/icons/icon/stop.svg';
import IconConfluence from '@/public/icons/logo/Confluence.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSlack from '@/public/icons/logo/Slack.svg';
import { SearchOptionButton } from '@/shared/components/SearchOptionButton';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

interface RagInputProps {
  filters: UseRagFiltersReturn;
  isLoading: boolean;
  onSendMessage: (message: string) => Promise<void>;
  onStop: () => void;
  onNewMessage: () => void;
}

export default function RagInput({ filters, isLoading, onSendMessage, onStop, onNewMessage }: RagInputProps) {
  const [newInput, setNewInput] = useState('');
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewInput(e.target.value);

    e.target.style.height = 'auto';
    const newHeight = Math.min(e.target.scrollHeight, 270);
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
    <div className="px-6 pt-8 pb-2.5 backdrop-blur-[10px] lg:px-24">
      <div className="mx-auto flex w-full max-w-194 flex-col items-center gap-2">
        {/* Text input 카드 */}
        <div className="border-edge-normal bg-fill-normal flex w-full flex-col rounded-2xl border p-4">
          {/* Filter Bar (카드 내부 상단) */}
          <div
            className={cn(
              'overflow-hidden transition-all duration-300 ease-in-out',
              filters.isFilterOpen ? 'mb-3 max-h-40 opacity-100' : 'max-h-0 opacity-0',
            )}
          >
            <div className="flex items-center gap-1.5">
              <Button
                variant="icon-outline-gray"
                size="md"
                type="button"
                onClick={filters.toggleFilter}
                aria-label="상세 검색 닫기"
              >
                <CancelSmall className="h-6 w-6" />
              </Button>
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
              {/* TODO: 담당자/부서/프로젝트 필터 — 백엔드 API 준비 후 주석 해제 */}
              {/*
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
              */}
            </div>
          </div>

          {/* Textarea */}
          <textarea
            ref={textAreaRef}
            placeholder="답은 이미 사내에 있어요. 바로 찾아드릴게요."
            value={newInput}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            className="text-body-medium text-content-normal placeholder:text-content-assistive w-full resize-none overflow-y-auto outline-none"
            style={{ height: '26px', maxHeight: '270px' }}
          />

          {/* 하단 컨트롤 바 */}
          <div className="mt-3 flex h-8 items-center justify-between">
            {/* 상세 검색 토글 */}
            <button
              type="button"
              onClick={filters.toggleFilter}
              className={cn(
                'text-content-neutral flex h-7 cursor-pointer items-center gap-1 rounded-full px-1.5 py-1',
                filters.isFilterOpen && 'bg-fill-interaction-pressed',
              )}
            >
              <SearchFile className="h-5 w-5 shrink-0" />
              <span className="text-body-xsmall">상세 검색</span>
            </button>

            {/* 전송 / 중지 버튼 */}
            {isLoading ? (
              <button
                onClick={onStop}
                className="bg-fill-interaction-disable flex h-10 w-10 items-center justify-center rounded-full"
              >
                <Stop className="text-content-neutral relative left-px h-6 w-6 cursor-pointer" />
              </button>
            ) : (
              <button
                onClick={handleSendMessage}
                disabled={isLoading || !newInput.trim()}
                className={cn(
                  'cursor-pointer rounded-full p-2 transition-colors',
                  newInput.trim()
                    ? 'bg-fill-primary'
                    : 'bg-fill-interaction-inactive border-edge-assistive border',
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

        {/* Helper 텍스트 */}
        <p className="text-label-xsmall text-content-alternative">
          출처를 기반으로 정보를 제공합니다. 자세한 내용은 원문을 확인해주세요.
        </p>
      </div>
    </div>
  );
}
