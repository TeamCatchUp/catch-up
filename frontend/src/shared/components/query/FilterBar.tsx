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

// eslint-disable-next-line @typescript-eslint/no-unused-vars -- inputRef는 필터 드롭다운 활성화 시 사용 예정
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
      {/* TODO: 백엔드 API 준비 시 담당자/부서/프로젝트 필터 드롭다운 활성화
      <IconDivider className="text-gray-5 h-6 w-6 shrink-0" />
      <div className="flex items-center gap-2.5">
        <FilterDropdown ...>
          <FilterOptionList title="담당자 선택" options={personOptions} ... />
        </FilterDropdown>
        <FilterDropdown ...>
          <FilterOptionList title="부서 선택" options={deptOptions} ... />
        </FilterDropdown>
        <FilterDropdown ...>
          <FilterOptionList title="프로젝트 선택" options={projectOptions} ... />
        </FilterDropdown>
      </div>
      */}
    </div>
  );
}
