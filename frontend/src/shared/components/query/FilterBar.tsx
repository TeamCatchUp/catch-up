'use client';

import { RefObject } from 'react';

import IconDivider from '@/public/icons/icon/divider.svg';
import IconLock from '@/public/icons/icon/lock_filled.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSlack from '@/public/icons/logo/Slack.svg'
import { FilterDropdown } from '@/shared/components/query/filter/FilterDropdown';
import { FilterOptionList } from '@/shared/components/query/filter/FilterOptionList';
import { SearchOptionButton, SearchOptionDisabledButton } from '@/shared/components/SearchOptionButton';
import type { UseSearchFiltersReturn } from '@/shared/hooks/query/useSearchFilters';
import { DEPARTMENT_OPTIONS, PERSON_OPTIONS, PROJECT_OPTIONS } from '@/shared/mocks/search/filterOptions';

interface FilterBarProps {
  filters: UseSearchFiltersReturn;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}

export default function FilterBar({ filters, inputRef }: FilterBarProps) {
  return (
    <div className="flex items-center gap-1.5 self-stretch overflow-x-scroll px-1.5 whitespace-nowrap">
      <div className="flex items-center gap-2">
        <SearchOptionButton Icon={IconJira} label="Jira" selected={filters.selectedSources.includes('jira')} onClick={() => filters.toggleSource('jira')} />
        <SearchOptionButton Icon={IconGithub} label="Github" selected={filters.selectedSources.includes('github')} onClick={() => filters.toggleSource('github')} />
        <SearchOptionButton Icon={IconSlack} label="Slack" selected={filters.selectedSources.includes('slack')} onClick={() => filters.toggleSource('slack')} />        
      </div>
      <IconDivider className="text-gray-5 h-6 w-6 shrink-0" />
      <div className="flex items-center gap-2">
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
            options={PERSON_OPTIONS}
            selected={filters.selectedPeople}
            onToggle={filters.togglePerson}
            Icon={IconPerson}
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
            options={DEPARTMENT_OPTIONS}
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
            options={PROJECT_OPTIONS}
            selected={filters.selectedProjects}
            onToggle={filters.toggleProject}
            Icon={IconSpace}
          />
        </FilterDropdown>
      </div>
    </div>
  );
}
