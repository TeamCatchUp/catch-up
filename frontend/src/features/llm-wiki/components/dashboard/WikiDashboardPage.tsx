'use client';

import type { DateRange } from 'react-day-picker';

import IconGrid from '@/public/icons/icon/grid.svg';
import IconKebabHorizontal from '@/public/icons/icon/kebab_horizontal.svg';
import { Button } from '@/shared/components/ui/button';

import type { DocumentRowData, KnownDocumentStatus, ReviewStatCardData } from '../../types/llmWikiModel';
import DashboardDocumentRow, { DashboardDocumentTableHeader } from '../document/DashboardDocumentRow';
import DocumentTableEmptyState from '../document/states/DocumentTableEmptyState';
import DocumentTableSkeleton from '../document/states/DocumentTableSkeleton';
import WikiPageHeader from '../header/WikiPageHeader';
import type { ReviewQueueFilterOption } from '../review-queue/ReviewQueueFilterSearchPanel';
import WikiSpaceTableFooter from '../space/WikiSpaceTableFooter';
import DashboardFilterBar from './DashboardFilterBar';
import {
  createAssigneeFilter,
  createCreatedAtFilter,
  createStatusFilter,
  type DashboardActiveFilter,
  type DashboardQueryState,
  getFilterAxis,
  INITIAL_DASHBOARD_QUERY_STATE,
  resolveStatFilter,
} from './dashboardFilters';
import ReviewStatCard from './ReviewStatCard';

interface WikiDashboardPageProps {
  stats: readonly ReviewStatCardData[];
  /** 서버가 이미 좁혀 준 한 쪽. 화면은 다시 거르지 않는다. */
  documents: readonly DocumentRowData[];
  /** 첫 조회가 끝나기 전인지. 쪽 이동은 이전 쪽을 그대로 두므로 여기 해당하지 않는다. */
  documentsLoading?: boolean;
  /** limit·offset을 걸기 전 문서 수 — 쪽 수 계산의 유일한 재료다. */
  totalCount: number;
  /** 담당자 후보. id는 담당자 user_id 문자열이다. */
  assigneeOptions: readonly ReviewQueueFilterOption[];
  /** "내 담당" 지표의 기준. 없으면 그 카드는 누를 수 없다. */
  myUserId?: number;
  pageSize: number;
  /** 조회 상태와 그 갱신 신호. 목록 요청은 소비처가 만든다. */
  queryState: DashboardQueryState;
  onQueryStateChange: (next: DashboardQueryState) => void;
  onDocumentClick?: (documentId: string) => void;
  /** 쪽 크기 선택. 소비처가 그 값을 들고 훅에 넘긴다. */
  onPageSizeChange?: (pageSize: number) => void;
  onMoreClick?: () => void;
}

/** LLM Wiki 대시보드 — 지표 카드 + 검색·필터 바 + 문서 표. */
export default function WikiDashboardPage({
  stats,
  documents,
  documentsLoading = false,
  totalCount,
  assigneeOptions,
  myUserId,
  pageSize,
  queryState,
  onQueryStateChange,
  onDocumentClick,
  onPageSizeChange,
  onMoreClick,
}: WikiDashboardPageProps) {
  const { filter, selectedAssigneeIds, createdAtRange, keyword, sortId, page } = queryState;

  // 필터는 한 번에 하나다 — 지표 카드와 드롭다운이 같은 자리를 놓고 서로를 덮어쓴다.
  const applyFilter = (
    next: DashboardActiveFilter | null,
    { assigneeIds = [], range }: { assigneeIds?: readonly string[]; range?: DateRange } = {},
  ) =>
    onQueryStateChange({
      ...queryState,
      filter: next,
      selectedAssigneeIds: assigneeIds,
      createdAtRange: range,
      page: 1,
    });

  const handleAssigneeToggle = (optionId: string) => {
    const nextIds = selectedAssigneeIds.includes(optionId)
      ? selectedAssigneeIds.filter((id) => id !== optionId)
      : [...selectedAssigneeIds, optionId];
    const selected = assigneeOptions.filter((option) => nextIds.includes(option.id));

    applyFilter(createAssigneeFilter(selected), { assigneeIds: nextIds });
  };

  const handleStatusSelect = (status: KnownDocumentStatus) => applyFilter(createStatusFilter(status));

  const handleCreatedAtChange = (range: DateRange | undefined) =>
    applyFilter(createCreatedAtFilter(range), { range });

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  return (
    <div className="flex flex-col">
      <WikiPageHeader
        variant="main"
        icon={<IconGrid />}
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
          {/* 지표 4종이 행을 나눠 갖는다 — 1040 = 245×4 + 20×3 */}
          <div className="grid grid-cols-4 gap-5">
            {stats.map((stat) => {
              const action = resolveStatFilter(stat.id, myUserId);

              return (
                <ReviewStatCard
                  key={stat.id}
                  stat={stat}
                  onClick={action ? () => applyFilter(action.filter) : undefined}
                />
              );
            })}
          </div>

          <DashboardFilterBar
            searchKeyword={keyword}
            sortId={sortId}
            onSortSelect={(nextSortId) => onQueryStateChange({ ...queryState, sortId: nextSortId, page: 1 })}
            createdAtRange={createdAtRange}
            onCreatedAtChange={handleCreatedAtChange}
            activeAxis={filter ? getFilterAxis(filter) : null}
            activeValueLabel={filter?.label}
            assigneeOptions={assigneeOptions}
            selectedAssigneeIds={selectedAssigneeIds}
            onAssigneeToggle={handleAssigneeToggle}
            onStatusSelect={handleStatusSelect}
            onSearchChange={(next) => onQueryStateChange({ ...queryState, keyword: next, page: 1 })}
            onClearFilters={() => onQueryStateChange(INITIAL_DASHBOARD_QUERY_STATE)}
          />

          <div className="flex flex-col gap-8">
            <div className="flex flex-col">
              <DashboardDocumentTableHeader />
              {documentsLoading ? (
                <DocumentTableSkeleton withPath />
              ) : documents.length === 0 ? (
                <DocumentTableEmptyState />
              ) : (
                <div className="flex flex-col gap-1">
                  {documents.map((document) => (
                    <DashboardDocumentRow key={document.id} document={document} onClick={onDocumentClick} />
                  ))}
                </div>
              )}
            </div>

            {/* 시안 우측에 같은 컨트롤이 하나 더 있으나 레이어명이 "Page Size (중복?)"이라 렌더하지 않는다 */}
            <WikiSpaceTableFooter
              pageSize={pageSize}
              currentPage={page}
              totalPages={totalPages}
              onPageChange={(nextPage) => onQueryStateChange({ ...queryState, page: nextPage })}
              onPageSizeChange={onPageSizeChange}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
