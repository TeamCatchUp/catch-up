'use client';

import type { ComponentType, SVGProps } from 'react';

import IconAlign from '@/public/icons/icon/align.svg';
import IconCalendar from '@/public/icons/icon/calendar.svg';
import IconCancelSmall from '@/public/icons/icon/cancel_small.svg';
import IconDashboard from '@/public/icons/icon/dashboard.svg';
import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconKebabHorizontal from '@/public/icons/icon/kebab_horizontal.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconProgress from '@/public/icons/icon/progress.svg';
import IconSearch from '@/public/icons/icon/search_300.svg';
import { Button } from '@/shared/components/ui/button';
import { Chip } from '@/shared/components/ui/chips';

import type { DocumentRowData, ReviewStatCardData } from '../../types/llmWikiModel';
import DashboardDocumentRow, { DashboardDocumentTableHeader } from '../document/DashboardDocumentRow';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiSpaceTableFooter from '../space/WikiSpaceTableFooter';
import ReviewStatCard from './ReviewStatCard';

/** 필터 축. 메뉴 시안이 없어 칩은 트리거까지만이고 열림 내용은 소비처 몫이다. */
export type DashboardFilterId = 'assignee' | 'status' | 'created-at';

const FILTER_CHIPS: readonly { id: DashboardFilterId; label: string; Icon: ComponentType<SVGProps<SVGSVGElement>> }[] = [
  { id: 'assignee', label: '담당자', Icon: IconPerson },
  { id: 'status', label: '상태', Icon: IconProgress },
  { id: 'created-at', label: '생성일', Icon: IconCalendar },
];

interface WikiDashboardPageProps {
  stats: readonly ReviewStatCardData[];
  documents: readonly DocumentRowData[];
  /** 정렬 칩 라벨. 옵션 목록 시안이 없어 현재값만 표시한다. */
  sortLabel: string;
  pageSize: number;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onDocumentClick?: (documentId: string) => void;
  onSearchChange?: (keyword: string) => void;
  onFilterClick?: (filterId: DashboardFilterId) => void;
  onSortClick?: () => void;
  onClearFilters?: () => void;
  onPageSizeClick?: () => void;
  onMoreClick?: () => void;
}

/** LLM Wiki 대시보드 — 지표 카드 + 검색·필터 바 + 문서 표. */
export default function WikiDashboardPage({
  stats,
  documents,
  sortLabel,
  pageSize,
  currentPage,
  totalPages,
  onPageChange,
  onDocumentClick,
  onSearchChange,
  onFilterClick,
  onSortClick,
  onClearFilters,
  onPageSizeClick,
  onMoreClick,
}: WikiDashboardPageProps) {
  return (
    <div className="flex flex-col">
      <WikiPageHeader
        variant="main"
        icon={<IconDashboard />}
        title="대시보드"
        actions={
          <Button variant="icon-only-gray" size="md" aria-label="더보기" onClick={onMoreClick}>
            <IconKebabHorizontal />
          </Button>
        }
      />

      {/* 본문 좌우 80은 헤더(64)와 다른 값이다 — 시안이 그렇게 갈라 둔다 */}
      <div className="flex flex-col gap-10 px-20 py-9">
        <div className="flex flex-col gap-1">
          <h1 className="text-heading-xlarge text-text-normal-normal">대시보드</h1>
          <p className="text-body-small text-text-normal-alternative">
            오늘 확인해야 할 지식과 최근 업데이트를 한곳에서 관리하세요.
          </p>
        </div>

        <div className="flex flex-col gap-6">
          {/* 4슬롯 그리드에 지표는 3종이다 — 마지막 슬롯이 비는 것이 현재 시안 상태다(디자이너 확인 대기) */}
          <div className="grid grid-cols-4 gap-4">
            {stats.map((stat) => (
              <ReviewStatCard key={stat.id} stat={stat} />
            ))}
          </div>

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
                    className="max-w-45 min-w-9 gap-2 px-2.5"
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
                  className="max-w-45 min-w-9 gap-2 px-2.5"
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

          <div className="flex flex-col gap-8">
            <div className="flex flex-col">
              <DashboardDocumentTableHeader />
              <div className="flex flex-col gap-1">
                {documents.map((document) => (
                  <DashboardDocumentRow key={document.id} document={document} onClick={onDocumentClick} />
                ))}
              </div>
            </div>

            {/* 시안 우측에 같은 컨트롤이 하나 더 있으나 레이어명이 "Page Size (중복?)"이라 렌더하지 않는다 */}
            <WikiSpaceTableFooter
              pageSize={pageSize}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={onPageChange}
              onPageSizeClick={onPageSizeClick}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
