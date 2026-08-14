'use client';

import { useMemo, useState } from 'react';

import IconDashboard from '@/public/icons/icon/dashboard.svg';
import IconKebabHorizontal from '@/public/icons/icon/kebab_horizontal.svg';
import { Button } from '@/shared/components/ui/button';

import type { DocumentRowData, KnownDocumentStatus, ReviewStatCardData } from '../../types/llmWikiModel';
import DashboardDocumentRow, { DashboardDocumentTableHeader } from '../document/DashboardDocumentRow';
import WikiPageHeader from '../header/WikiPageHeader';
import type { ReviewQueueFilterOption } from '../review-queue/ReviewQueueFilterSearchPanel';
import WikiSpaceTableFooter from '../space/WikiSpaceTableFooter';
import DashboardFilterBar from './DashboardFilterBar';
import {
  createAssigneeFilter,
  createStatusFilter,
  type DashboardActiveFilter,
  filterDocuments,
  findStatFilter,
} from './dashboardFilters';
import ReviewStatCard from './ReviewStatCard';

interface WikiDashboardPageProps {
  stats: readonly ReviewStatCardData[];
  documents: readonly DocumentRowData[];
  /** "내 담당" 필터의 기준. 로그인 사용자 API가 없어 주입받는다. */
  currentUserName: string;
  assigneeOptions: readonly ReviewQueueFilterOption[];
  sortLabel: string;
  pageSize: number;
  onDocumentClick?: (documentId: string) => void;
  onSortClick?: () => void;
  onCreatedAtClick?: () => void;
  onPageSizeClick?: () => void;
  onMoreClick?: () => void;
}

/** LLM Wiki 대시보드 — 지표 카드 + 검색·필터 바 + 문서 표. */
export default function WikiDashboardPage({
  stats,
  documents,
  currentUserName,
  assigneeOptions,
  sortLabel,
  pageSize,
  onDocumentClick,
  onSortClick,
  onCreatedAtClick,
  onPageSizeClick,
  onMoreClick,
}: WikiDashboardPageProps) {
  // 필터는 한 번에 하나다 — 지표 카드와 드롭다운이 같은 자리를 놓고 서로를 덮어쓴다.
  const [activeFilter, setActiveFilter] = useState<DashboardActiveFilter | null>(null);
  const [selectedAssigneeIds, setSelectedAssigneeIds] = useState<readonly string[]>([]);
  const [keyword, setKeyword] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  const applyFilter = (next: DashboardActiveFilter | null, assigneeIds: readonly string[] = []) => {
    setSelectedAssigneeIds(assigneeIds);
    setActiveFilter(next);
    setCurrentPage(1);
  };

  const handleAssigneeToggle = (optionId: string) => {
    const nextIds = selectedAssigneeIds.includes(optionId)
      ? selectedAssigneeIds.filter((id) => id !== optionId)
      : [...selectedAssigneeIds, optionId];
    const names = assigneeOptions.filter((option) => nextIds.includes(option.id)).map((option) => option.label);

    applyFilter(createAssigneeFilter(names), nextIds);
  };

  const handleStatusSelect = (status: KnownDocumentStatus) => applyFilter(createStatusFilter(status));

  const visibleDocuments = useMemo(() => {
    const filtered = filterDocuments(documents, activeFilter, currentUserName);
    const needle = keyword.trim().toLowerCase();
    // 검색은 제목 대조다 — 본문·태그 검색은 계약이 없다.
    return needle ? filtered.filter((row) => row.title.toLowerCase().includes(needle)) : filtered;
  }, [activeFilter, currentUserName, documents, keyword]);

  const totalPages = Math.max(1, Math.ceil(visibleDocuments.length / pageSize));

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
            {stats.map((stat) => {
              const statFilter = findStatFilter(stat.id);

              return (
                <ReviewStatCard
                  key={stat.id}
                  stat={stat}
                  onClick={statFilter ? () => applyFilter(statFilter) : undefined}
                />
              );
            })}
          </div>

          <DashboardFilterBar
            sortLabel={sortLabel}
            activeAxis={activeFilter?.axis ?? null}
            activeValueLabel={activeFilter?.label}
            assigneeOptions={assigneeOptions}
            selectedAssigneeIds={selectedAssigneeIds}
            onAssigneeToggle={handleAssigneeToggle}
            onStatusSelect={handleStatusSelect}
            onSearchChange={(next) => {
              setKeyword(next);
              setCurrentPage(1);
            }}
            onCreatedAtClick={onCreatedAtClick}
            onSortClick={onSortClick}
            onClearFilters={() => {
              setKeyword('');
              applyFilter(null);
            }}
          />

          <div className="flex flex-col gap-8">
            <div className="flex flex-col">
              <DashboardDocumentTableHeader />
              <div className="flex flex-col gap-1">
                {visibleDocuments.map((document) => (
                  <DashboardDocumentRow key={document.id} document={document} onClick={onDocumentClick} />
                ))}
              </div>
            </div>

            {/* 시안 우측에 같은 컨트롤이 하나 더 있으나 레이어명이 "Page Size (중복?)"이라 렌더하지 않는다 */}
            <WikiSpaceTableFooter
              pageSize={pageSize}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
              onPageSizeClick={onPageSizeClick}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
