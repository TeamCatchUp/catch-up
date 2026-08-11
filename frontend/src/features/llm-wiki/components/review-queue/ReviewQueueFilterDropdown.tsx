'use client';

import type { ComponentType, SVGProps } from 'react';

import IconArrowRight from '@/public/icons/icon/arrow_right.svg';
import IconFilterList from '@/public/icons/icon/filter_list.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';

export interface ReviewQueueFilterOption {
  id: string;
  label: string;
}

export interface ReviewQueueFilterSection {
  id: string;
  label: string;
  options: readonly ReviewQueueFilterOption[];
  /** 축 좌측 아이콘. 축 자체가 props 주입이므로 아이콘도 주입받는다. */
  Icon?: ComponentType<SVGProps<SVGSVGElement>>;
}

interface ReviewQueueFilterDropdownProps {
  sections: readonly ReviewQueueFilterSection[];
  onSelect?: (sectionId: string, optionId: string) => void;
}

/**
 * 검토 큐 툴바의 필터 아이콘 버튼과 그 메뉴. 축은 평면 목록이 아니라 서브메뉴 트리거다.
 * 축·옵션 목록은 전부 props로 받는다 — 컴포넌트가 정하지 않는다.
 */
export default function ReviewQueueFilterDropdown({ sections, onSelect }: ReviewQueueFilterDropdownProps) {
  return (
    <DropdownMenu>
      {/* 아이콘 전용 트리거 — 컨트롤 크기라 정사각으로 고정한다. */}
      <DropdownMenuTrigger
        aria-label="필터"
        className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex size-9 cursor-pointer items-center justify-center rounded-lg border"
      >
        <IconFilterList aria-hidden className="text-icon-normal-neutral size-6" />
      </DropdownMenuTrigger>

      {/* 카드 폭은 고정이다 — 공용 래퍼 기본값만으로는 긴 라벨에서 늘어난다. */}
      <DropdownMenuContent align="start" className="w-50">
        {sections.map(({ id, label, options, Icon }) => (
          <DropdownMenuSub key={id}>
            {/* 항목 높이는 패딩+아이콘의 결과값이다 — h-*로 못박지 않는다. */}
            <DropdownMenuSubTrigger className="gap-1">
              <span className="flex min-w-0 flex-1 items-center gap-2.5">
                {Icon && <Icon aria-hidden className="text-icon-normal-normal size-6 shrink-0" />}
                <span className="min-w-0 flex-1 truncate">{label}</span>
              </span>
              <IconArrowRight aria-hidden className="text-icon-normal-alternative size-6 shrink-0" />
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              {options.map((option) => (
                <DropdownMenuItem key={option.id} onSelect={() => onSelect?.(id, option.id)}>
                  <span className="min-w-0 flex-1 truncate">{option.label}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
