'use client';

import type { ComponentProps, ComponentType, ReactNode, SVGProps } from 'react';
import type { DateRange } from 'react-day-picker';

import IconAlign from '@/public/icons/icon/align.svg';
import IconCalendar from '@/public/icons/icon/calendar.svg';
import IconCancelSmall from '@/public/icons/icon/cancel_small.svg';
import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconPersonFilled from '@/public/icons/icon/person_filled.svg';
import IconProgress from '@/public/icons/icon/progress.svg';
import IconSearch from '@/public/icons/icon/search_300.svg';
import { Chip } from '@/shared/components/ui/chips';
import { DateRangePicker } from '@/shared/components/ui/date-range-picker';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import type { KnownDocumentStatus } from '../../types/llmWikiModel';
import DocumentStatusBadge from '../document/DocumentStatusBadge';
import ReviewQueueFilterSearchPanel, {
  type ReviewQueueFilterOption,
} from '../review-queue/ReviewQueueFilterSearchPanel';
import {
  DASHBOARD_SORT_OPTIONS,
  DASHBOARD_STATUS_OPTIONS,
  type DashboardSortId,
  getSortLabel,
} from './dashboardFilters';

/** 필터 축. 생성일은 캘린더 시안이 별도라 아직 트리거까지만이다. */
export type DashboardFilterId = 'assignee' | 'status' | 'created-at';

/** 칩 기하는 시안값이고 색은 shared Chip의 square 변형을 그대로 쓴다. */
const CHIP_CLASS = 'max-w-45 min-w-9 gap-2 px-2.5';

interface ChipLabelProps {
  axisLabel: string;
  valueLabel?: string;
}

/** 활성 칩은 "축: 값"으로 적힌다 — 축만 남기면 담당자 축의 두 값이 구분되지 않는다. */
function ChipLabel({ axisLabel, valueLabel }: ChipLabelProps) {
  if (!valueLabel) return <>{axisLabel}</>;

  return (
    <span className="flex min-w-0 items-center gap-2">
      <span className="shrink-0">{axisLabel}:</span>
      <span className="min-w-0 flex-1 truncate">{valueLabel}</span>
    </span>
  );
}

type FilterChipProps = ComponentProps<typeof Chip> & {
  axisLabel: string;
  valueLabel?: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
};

/** rest를 그대로 넘긴다 — 드롭다운 트리거로 쓸 때 Radix가 얹는 ref·aria가 여기서 끊기면 메뉴가 열리지 않는다. */
function FilterChip({ axisLabel, valueLabel, Icon, ...rest }: FilterChipProps) {
  return (
    <Chip
      {...rest}
      variant="square"
      selected={Boolean(valueLabel)}
      leadingIcon={<Icon />}
      trailingIcon={<IconDropdownDown />}
      className={CHIP_CLASS}
    >
      <ChipLabel axisLabel={axisLabel} valueLabel={valueLabel} />
    </Chip>
  );
}

/** 드롭다운 카드는 축마다 폭만 다르고 나머지 기하는 같다. */
function FilterDropdown({ trigger, width, children }: { trigger: ReactNode; width: string; children: ReactNode }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent align="start" className={`${width} rounded-xl`}>
        {children}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

interface DashboardFilterBarProps {
  sortId: DashboardSortId;
  onSortSelect: (sortId: DashboardSortId) => void;
  /** 생성일 범위. 공용 DateRangePicker가 캘린더를 그린다. */
  createdAtRange?: DateRange;
  onCreatedAtChange: (range: DateRange | undefined) => void;
  /** 활성 필터 — 해당 축 칩이 선택 톤이 되고 "축: 값"으로 표기된다. */
  activeAxis?: DashboardFilterId | null;
  activeValueLabel?: string;
  /** 담당자 축 옵션과 현재 선택. 검토 큐와 같은 검색 패널을 쓴다. */
  assigneeOptions: readonly ReviewQueueFilterOption[];
  selectedAssigneeIds: readonly string[];
  onAssigneeToggle: (optionId: string) => void;
  onStatusSelect: (status: KnownDocumentStatus) => void;
  onSearchChange?: (keyword: string) => void;
  onClearFilters?: () => void;
}

/** 대시보드 문서 표 위의 검색·필터 바. 축 목록은 시안 실재 3종으로 고정이다. */
export default function DashboardFilterBar({
  sortId,
  onSortSelect,
  createdAtRange,
  onCreatedAtChange,
  activeAxis,
  activeValueLabel,
  assigneeOptions,
  selectedAssigneeIds,
  onAssigneeToggle,
  onStatusSelect,
  onSearchChange,
  onClearFilters,
}: DashboardFilterBarProps) {
  const valueOf = (axis: DashboardFilterId) => (activeAxis === axis ? activeValueLabel : undefined);

  return (
    <div className="border-line-normal-neutral bg-fill-normal-assistive flex flex-col gap-3 rounded-xl border p-5">
      {/* 검색창 — 공용 Input에는 아이콘 슬롯이 없어 같은 토큰으로 직접 조립한다 */}
      <div className="bg-fill-normal-strong border-line-normal-assistive focus-within:border-line-primary-normal flex min-h-10 items-center gap-2 rounded-lg border px-3 py-2">
        <IconSearch aria-hidden className="text-icon-normal-alternative size-5 shrink-0" />
        <input
          type="text"
          placeholder="검색어를 입력하세요."
          aria-label="문서 검색"
          onChange={(event) => onSearchChange?.(event.target.value)}
          className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive min-w-0 flex-1 bg-transparent outline-none"
        />
      </div>

      <div className="flex items-center gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          {/* 담당자 — 검토 큐와 같은 검색 멀티셀렉트 패널(시안 노드도 같은 구조다) */}
          <FilterDropdown
            width="w-75"
            trigger={<FilterChip axisLabel="담당자" valueLabel={valueOf('assignee')} Icon={IconPerson} />}
          >
            <div onKeyDown={(event) => event.stopPropagation()}>
              <ReviewQueueFilterSearchPanel
                options={assigneeOptions}
                selectedIds={selectedAssigneeIds}
                onToggle={onAssigneeToggle}
                placeholder="담당자 검색"
                OptionIcon={IconPersonFilled}
              />
            </div>
          </FilterDropdown>

          {/* 상태 — 옵션이 배지 그 자체다. 하나만 고를 수 있고 해제는 "필터 초기화"가 맡는다 */}
          <FilterDropdown
            width="w-62.5"
            trigger={<FilterChip axisLabel="상태" valueLabel={valueOf('status')} Icon={IconProgress} />}
          >
            {DASHBOARD_STATUS_OPTIONS.map((status) => (
              <DropdownMenuItem key={status} onSelect={() => onStatusSelect(status)} className="h-10">
                <DocumentStatusBadge status={status} />
              </DropdownMenuItem>
            ))}
          </FilterDropdown>

          {/* 생성일 — 공용 DateRangePicker가 캘린더·액션 바를 그리고 칩은 트리거만 맡는다 */}
          <DateRangePicker
            value={createdAtRange}
            onChange={onCreatedAtChange}
            align="start"
            trigger={<FilterChip axisLabel="생성일" valueLabel={valueOf('created-at')} Icon={IconCalendar} />}
          />

          {/* 정렬 칩만 항상 선택 톤이다 — 정렬은 늘 걸려 있다 */}
          <FilterDropdown
            width="w-62.5"
            trigger={
              <Chip
                variant="square"
                selected
                leadingIcon={<IconAlign />}
                trailingIcon={<IconDropdownDown />}
                className={CHIP_CLASS}
              >
                {getSortLabel(sortId)}
              </Chip>
            }
          >
            {DASHBOARD_SORT_OPTIONS.map((option) => (
              <DropdownMenuItem
                key={option.id}
                onSelect={() => onSortSelect(option.id)}
                className={cn('h-10', option.id === sortId && 'bg-fill-normal-interaction-hover')}
              >
                <span className="min-w-0 flex-1 truncate">{option.label}</span>
              </DropdownMenuItem>
            ))}
          </FilterDropdown>
        </div>

        <button
          type="button"
          onClick={onClearFilters}
          className="text-heading-small text-text-normal-alternative hover:bg-fill-normal-interaction-hover flex h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1"
        >
          <IconCancelSmall aria-hidden className="text-icon-normal-neutral size-5 shrink-0" />
          필터 초기화
        </button>
      </div>
    </div>
  );
}
