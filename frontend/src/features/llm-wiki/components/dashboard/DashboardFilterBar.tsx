'use client';

import type { ComponentType, SVGProps } from 'react';

import IconAlign from '@/public/icons/icon/align.svg';
import IconCalendar from '@/public/icons/icon/calendar.svg';
import IconCancelSmall from '@/public/icons/icon/cancel_small.svg';
import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconProgress from '@/public/icons/icon/progress.svg';
import IconSearch from '@/public/icons/icon/search_300.svg';
import { Chip } from '@/shared/components/ui/chips';

/** 필터 축. 메뉴 시안이 없어 칩은 트리거까지만이고 열림 내용은 소비처 몫이다. */
export type DashboardFilterId = 'assignee' | 'status' | 'created-at';

const FILTER_CHIPS: readonly { id: DashboardFilterId; label: string; Icon: ComponentType<SVGProps<SVGSVGElement>> }[] = [
  { id: 'assignee', label: '담당자', Icon: IconPerson },
  { id: 'status', label: '상태', Icon: IconProgress },
  { id: 'created-at', label: '생성일', Icon: IconCalendar },
];

/** 칩 기하는 시안값이고 색은 shared Chip의 square 변형을 그대로 쓴다. */
const CHIP_CLASS = 'max-w-45 min-w-9 gap-2 px-2.5';

interface DashboardFilterBarProps {
  /** 정렬 칩 라벨. 옵션 목록 시안이 없어 현재값만 표시한다. */
  sortLabel: string;
  onSearchChange?: (keyword: string) => void;
  onFilterClick?: (filterId: DashboardFilterId) => void;
  onSortClick?: () => void;
  onClearFilters?: () => void;
}

/** 대시보드 문서 표 위의 검색·필터 바. 축 목록은 시안 실재 3종으로 고정이다. */
export default function DashboardFilterBar({
  sortLabel,
  onSearchChange,
  onFilterClick,
  onSortClick,
  onClearFilters,
}: DashboardFilterBarProps) {
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
          {FILTER_CHIPS.map(({ id, label, Icon }) => (
            <Chip
              key={id}
              variant="square"
              onClick={() => onFilterClick?.(id)}
              leadingIcon={<Icon />}
              trailingIcon={<IconDropdownDown />}
              className={CHIP_CLASS}
            >
              {label}
            </Chip>
          ))}

          {/* 정렬 칩만 selected 톤이다 — 항상 정렬이 걸려 있기 때문 */}
          <Chip
            variant="square"
            selected
            onClick={onSortClick}
            leadingIcon={<IconAlign />}
            trailingIcon={<IconDropdownDown />}
            className={CHIP_CLASS}
          >
            {sortLabel}
          </Chip>
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
