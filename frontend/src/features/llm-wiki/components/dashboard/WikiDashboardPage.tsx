'use client';

import IconDashboard from '@/public/icons/icon/dashboard.svg';
import IconKebabHorizontal from '@/public/icons/icon/kebab_horizontal.svg';
import { Button } from '@/shared/components/ui/button';

import type { DocumentRowData, ReviewStatCardData } from '../../types/llmWikiModel';
import DashboardDocumentRow, { DashboardDocumentTableHeader } from '../document/DashboardDocumentRow';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiSpaceTableFooter from '../space/WikiSpaceTableFooter';
import DashboardFilterBar, { type DashboardFilterId } from './DashboardFilterBar';
import ReviewStatCard from './ReviewStatCard';

interface WikiDashboardPageProps {
  stats: readonly ReviewStatCardData[];
  documents: readonly DocumentRowData[];
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

          <DashboardFilterBar
            sortLabel={sortLabel}
            onSearchChange={onSearchChange}
            onFilterClick={onFilterClick}
            onSortClick={onSortClick}
            onClearFilters={onClearFilters}
          />

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
