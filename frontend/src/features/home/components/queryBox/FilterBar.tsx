'use client';

import { RefObject } from 'react';
import type { UseSearchFiltersReturn } from '@/features/search/hooks/useSearchFilters';

import IconJira from '@/public/icons/logo/Jira.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconDivider from '@/public/icons/icon/divider.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconLock from '@/public/icons/icon/lock_filled.svg';

import { SearchOptionButton, SearchOptionDisabledButton } from '@/shared/components/SearchOptionButton';
import { FilterDropdown } from '@/features/search/components/filter/FilterDropdown';
import { FilterOptionList } from '@/features/search/components/filter/FilterOptionList';
import { PERSON_OPTIONS } from '@/shared/mocks/search/filterOptions';

interface FilterBarProps {
  filters: UseSearchFiltersReturn;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}

export default function FilterBar({ filters, inputRef }: FilterBarProps) {
  return (
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
  );
}
