'use client';

import { RefObject } from 'react';

import IconConfluence from '@/public/icons/logo/Confluence.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSlack from '@/public/icons/logo/Slack.svg';
import { SearchOptionButton } from '@/shared/components/SearchOptionButton';
import type { UseSearchFiltersReturn } from '@/shared/hooks/query/useSearchFilters';

interface FilterBarProps {
  filters: UseSearchFiltersReturn;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}

export default function FilterBar({ filters, inputRef }: FilterBarProps) {
  return (
    <div className="flex items-center gap-2.5 self-stretch overflow-x-scroll py-0.5 whitespace-nowrap">
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
      {/* <IconDivider className="text-gray-5 h-6 w-6 shrink-0" />
      <div className="flex items-center gap-2.5">
        <FilterDropdown
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
          <FilterOptionList
            title="담당자 선택"
            options={MOCK_PERSON_FILTER_OPTIONS}
            selected={filters.selectedPeople}
            onToggle={filters.togglePerson}
            Icon={IconProfile}
          />
        </FilterDropdown>
        <FilterDropdown
          open={filters.openPopover === 'department'}
          onOpenChange={(o) => {
            filters.setOpenPopover(o ? 'department' : null);
            if (!o) inputRef.current?.focus();
          }}
          trigger={
            <SearchOptionButton
              Icon={IconTag}
              label={filters.labels.dept}
              selected={filters.selectedDepts.length > 0}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => filters.setOpenPopover('department')}
            />
          }
        >
          <FilterOptionList
            title="부서 선택"
            options={MOCK_DEPARTMENT_FILTER_OPTIONS}
            selected={filters.selectedDepts}
            onToggle={filters.toggleDept}
            Icon={IconTag}
          />
        </FilterDropdown>
        <FilterDropdown
          open={filters.openPopover === 'project'}
          onOpenChange={(o) => {
            filters.setOpenPopover(o ? 'project' : null);
            if (!o) inputRef.current?.focus();
          }}
          trigger={
            <SearchOptionButton
              Icon={IconSpace}
              label={filters.labels.project}
              selected={filters.selectedProjects.length > 0}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => filters.setOpenPopover('project')}
            />
          }
        >
          <FilterOptionList
            title="프로젝트 선택"
            options={MOCK_PROJECT_FILTER_OPTIONS}
            selected={filters.selectedProjects}
            onToggle={filters.toggleProject}
            Icon={IconSpace}
          />
        </FilterDropdown>
      </div> */}
    </div>
  );
}
