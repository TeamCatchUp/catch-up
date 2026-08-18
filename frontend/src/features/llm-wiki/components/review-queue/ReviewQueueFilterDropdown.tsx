'use client';

import type { ComponentType, SVGProps } from 'react';

import IconArrowRight from '@/public/icons/icon/arrow_right.svg';
import IconFilterList from '@/public/icons/icon/filter_list.svg';
import IconFilterListFilled from '@/public/icons/icon/filter_list_filled.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import ReviewQueueFilterSearchPanel, { type ReviewQueueFilterOption } from './ReviewQueueFilterSearchPanel';

export type { ReviewQueueFilterOption };

export interface ReviewQueueFilterSection {
  id: string;
  label: string;
  options: readonly ReviewQueueFilterOption[];
  /** 축 좌측 아이콘. 축 자체가 props 주입이므로 아이콘도 주입받는다. */
  Icon?: ComponentType<SVGProps<SVGSVGElement>>;
  /** 축의 현재값 요약(예: "전체"). 축 행 우측, 화살표 앞에 놓인다. */
  valueLabel?: string;
  /** 단일 선택 축의 현재 적용 옵션. 옵션 목록에서 지속 하이라이트된다. */
  selectedOptionId?: string;
  /** 값이 있으면 검색 멀티셀렉트 축이 되고, 이 문자열이 검색창 placeholder다. */
  searchPlaceholder?: string;
  /** 검색 멀티셀렉트 축의 현재 선택 목록. valueLabel을 주지 않으면 여기서 요약을 만든다. */
  selectedOptionIds?: readonly string[];
  /** 검색 패널의 옵션 글리프. 없으면 축 아이콘을 쓴다. */
  OptionIcon?: ComponentType<SVGProps<SVGSVGElement>>;
}

interface ReviewQueueFilterDropdownProps {
  sections: readonly ReviewQueueFilterSection[];
  /** 단일 선택 축의 선택 신호. */
  onSelect?: (sectionId: string, optionId: string) => void;
  /** 검색 멀티셀렉트 축의 선택·해제 신호. 이미 선택된 id가 오면 해제다. */
  onToggle?: (sectionId: string, optionId: string) => void;
  /** 필터가 걸려 있으면 트리거 글리프가 파란 원형(filled)으로 바뀐다. */
  filtered?: boolean;
}

/**
 * 검토 큐 툴바의 필터 아이콘 버튼과 그 메뉴. 축은 평면 목록이 아니라 서브메뉴 트리거다.
 * 축·옵션 목록은 전부 props로 받는다 — 컴포넌트가 정하지 않는다.
 */
export default function ReviewQueueFilterDropdown({
  sections,
  onSelect,
  onToggle,
  filtered = false,
}: ReviewQueueFilterDropdownProps) {
  return (
    <DropdownMenu>
      {/* 아이콘 전용 트리거 — 컨트롤 크기라 정사각으로 고정한다. */}
      <DropdownMenuTrigger
        aria-label="필터"
        className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover data-[state=open]:border-line-normal-strong data-[state=open]:bg-fill-normal-interaction-pressed flex size-9 cursor-pointer items-center justify-center rounded-lg border"
      >
        {filtered ? (
          <IconFilterListFilled aria-hidden className="text-icon-primary-normal size-6" />
        ) : (
          <IconFilterList aria-hidden className="text-icon-normal-neutral size-6" />
        )}
      </DropdownMenuTrigger>

      {/* 카드 폭 250·radius 12는 시안 고정값 — 래퍼 기본(min-w 200·radius 16)을 덮는다. */}
      <DropdownMenuContent align="start" className="w-62.5 rounded-xl">
        {sections.map((section) => {
          const { id, label, options, Icon, selectedOptionId, searchPlaceholder, selectedOptionIds, OptionIcon } =
            section;
          const selectedIds = selectedOptionIds ?? [];
          // 검색 축의 요약은 선택 목록에서 파생한다 — 소비처가 같은 문자열을 두 번 만들지 않게.
          const valueLabel =
            section.valueLabel ??
            (selectedIds.length > 0
              ? options
                  .filter((option) => selectedIds.includes(option.id))
                  .map((option) => option.label)
                  .join(', ')
              : undefined);

          return (
            <DropdownMenuSub key={id}>
              {/* 항목 높이 31은 패딩 4+텍스트 23의 결과다 — 공용 래퍼 기본(py-2)이면 40이 된다 */}
              <DropdownMenuSubTrigger className="gap-1 py-1">
                <span className="flex min-w-0 flex-1 items-center gap-2.5">
                  {Icon && <Icon aria-hidden className="text-icon-normal-normal size-5 shrink-0" />}
                  <span className="min-w-0 flex-1 truncate">{label}</span>
                </span>
                {valueLabel && (
                  <span className="text-body-xsmall text-text-normal-alternative max-w-19.5 shrink-0 truncate">
                    {valueLabel}
                  </span>
                )}
                <IconArrowRight aria-hidden className="text-icon-normal-alternative size-5 shrink-0" />
              </DropdownMenuSubTrigger>

              {searchPlaceholder ? (
                <DropdownMenuSubContent className="shadow-modal w-75 rounded-xl px-0 py-2.5">
                  {/* Radix 메뉴의 타이핑 탐색이 검색 입력을 가로채므로 여기서 키를 끊는다 */}
                  <div onKeyDown={(event) => event.stopPropagation()}>
                    <ReviewQueueFilterSearchPanel
                      options={options}
                      selectedIds={selectedIds}
                      onToggle={(optionId) => onToggle?.(id, optionId)}
                      placeholder={searchPlaceholder}
                      OptionIcon={OptionIcon ?? Icon ?? IconFilterList}
                    />
                  </div>
                </DropdownMenuSubContent>
              ) : (
                <DropdownMenuSubContent className="w-50 rounded-xl">
                  {options.map((option) => (
                    <DropdownMenuItem
                      key={option.id}
                      onSelect={() => onSelect?.(id, option.id)}
                      className={cn('py-1', option.id === selectedOptionId && 'bg-fill-normal-interaction-hover')}
                    >
                      <span className="min-w-0 flex-1 truncate">{option.label}</span>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuSubContent>
              )}
            </DropdownMenuSub>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
