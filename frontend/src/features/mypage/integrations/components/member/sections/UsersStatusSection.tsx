'use client';

import { useCallback, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';

import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import { Button } from '@/shared/components/ui/button';
import Pagination from '@/shared/components/ui/pagination';
import { cn } from '@/shared/utils/cn';

import type { SyncFilterType } from '../../../types/api';
import type { IntegrationService } from '../../../types/integrations';
import type { MemberDisplayRow } from '../../../types/memberDisplay';
import type { AccountOption } from '../tables/AccountSelectDropdown';
import UsersTable from '../tables/UsersTable';

const CsvUploadModal = dynamic(() => import('../modals/CsvUploadModal'));

const PAGE_SIZE = 10;
const EMPTY_ACCOUNT_OPTIONS: Partial<Record<IntegrationService, AccountOption[]>> = {};

interface UsersStatusSectionProps {
  total: number;
  displayRows: MemberDisplayRow[];
  filterType: SyncFilterType;
  onFilterChange: (type: SyncFilterType) => void;
  currentPage: number;
  onPageChange: (page: number) => void;
}

const FILTER_OPTIONS: { key: SyncFilterType; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'full', label: '모두 연동된 이용자' },
  { key: 'partial', label: '연동되지 않은 이용자' },
];

/** 이용자 계정 연동 상태 섹션 */
const UsersStatusSection = ({
  total,
  displayRows,
  filterType,
  onFilterChange,
  currentPage,
  onPageChange,
}: UsersStatusSectionProps) => {
  const [isEditMode, setIsEditMode] = useState(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);

  // 수정 모드에서 계정 선택 / 미사용 토글 로컬 오버라이드
  type AccountOverride = { type: 'account'; account: AccountOption } | { type: 'unused' };
  const [overrides, setOverrides] = useState<Record<string, Partial<Record<IntegrationService, AccountOverride>>>>({});

  const handleAccountSelect = useCallback((userKey: string, service: IntegrationService, account: AccountOption) => {
    setOverrides((prev) => ({
      ...prev,
      [userKey]: { ...prev[userKey], [service]: { type: 'account', account } },
    }));
  }, []);

  const handleToggleUnused = useCallback((userKey: string, service: IntegrationService, unused: boolean) => {
    setOverrides((prev) => {
      const userOverrides = { ...prev[userKey] };
      if (unused) {
        userOverrides[service] = { type: 'unused' };
      } else {
        delete userOverrides[service];
      }
      return { ...prev, [userKey]: userOverrides };
    });
  }, []);

  // 오버라이드 적용된 행
  const effectiveRows = useMemo(() => {
    if (Object.keys(overrides).length === 0) return displayRows;

    return displayRows.map((displayRow) => {
      const userOverrides = overrides[displayRow.row.userKey];
      if (!userOverrides) return displayRow;

      const newStatus = { ...displayRow.displayStatusByService };

      for (const [service, override] of Object.entries(userOverrides) as [IntegrationService, AccountOverride][]) {
        if (override.type === 'account') {
          newStatus[service] = '완료';
        } else {
          newStatus[service] = '미사용';
        }
      }

      return {
        ...displayRow,
        displayStatusByService: newStatus,
      };
    });
  }, [displayRows, overrides]);

  // 서버 사이드 페이지네이션
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="flex w-250 flex-col gap-3">
      {/* 헤더: 제목 + 설명 */}
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-gray-80">
          이용자 계정 등록 상태 <span className="text-blue-40">{total}</span>
        </h2>
        <p className="text-body-small text-gray-50">Catch Up 사용자의 협업 툴 계정 등록 상태를 확인할 수 있어요.</p>
      </div>

      {/* 필터 칩 + 버튼 영역 */}
      <div className="flex items-center justify-between gap-3">
        {/* 필터 칩 */}
        <div className="flex items-center gap-2">
          {FILTER_OPTIONS.map(({ key, label }) => {
            const isSelected = filterType === key;

            return (
              <button
                key={key}
                onClick={() => onFilterChange(key)}
                className={cn(
                  'text-body-small h-9 cursor-pointer rounded-full border px-3 py-1.5 transition-colors',
                  isSelected ? 'bg-neutral-80 border-transparent text-white' : 'border-neutral-3 text-gray-60',
                )}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* 버튼 영역 */}
        <div className="flex items-center gap-2">
          <Button
            variant="box-outline-gray"
            size="md"
            className="text-body-small h-9"
            onClick={() => setIsCsvModalOpen(true)}
          >
            CSV 일괄등록
          </Button>

          {isEditMode ? (
            <Button
              variant="box-solid-primary"
              size="md"
              className="text-body-small h-9"
              onClick={() => setIsEditMode(false)}
            >
              저장하기
            </Button>
          ) : (
            <Button
              variant="box-outline-gray"
              size="md"
              className="text-body-small flex h-9 items-center gap-1.5"
              onClick={() => setIsEditMode(true)}
            >
              <IconEditPencil className="h-4 w-4" />
              수정하기
            </Button>
          )}
        </div>
      </div>

      {/* 테이블 */}
      <div className="border-neutral-3 w-250 border-y">
        <UsersTable
          displayRows={effectiveRows}
          isEditMode={isEditMode}
          accountOptionsByService={EMPTY_ACCOUNT_OPTIONS}
          onAccountSelect={handleAccountSelect}
          onToggleUnused={handleToggleUnused}
        />
      </div>

      {/* 페이지네이션 + 범례 */}
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex-1" />
        {totalPages > 1 && <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />}
        <div className="flex flex-1 items-center justify-end gap-6">
          <div className="flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-green-50" />
            <p className="text-body-small text-gray-50">모두 연동된 이용자</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="bg-red-40 h-2.5 w-2.5 rounded-full" />
            <p className="text-body-small text-gray-50">연동되지 않은 이용자</p>
          </div>
        </div>
      </div>

      {/* CSV 업로드 모달 */}
      <CsvUploadModal open={isCsvModalOpen} onOpenChange={setIsCsvModalOpen} />
    </section>
  );
};

export default UsersStatusSection;
