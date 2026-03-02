'use client';

import { useCallback, useMemo, useState } from 'react';

import { useMemberIntegrationViewModel } from '../../../hooks/useMemberIntegrationViewModel';
import type { SyncFilterType } from '../../../types/api';
import { buildMemberDisplayRows } from '../../../utils/memberDisplay';
import StatusCardsSection from './StatusCardsSection';
import UsersStatusSection from './UsersStatusSection';

const PAGE_SIZE = 10;

/** 관리자 이용자 연동 탭 섹션 */
const IntegrationsSection = () => {
  const [filterType, setFilterType] = useState<SyncFilterType>('all');
  const [currentPage, setCurrentPage] = useState(1);

  const { cards, rows, total } = useMemberIntegrationViewModel({
    filterType,
    page: currentPage,
    size: PAGE_SIZE,
  });

  const displayRows = useMemo(() => buildMemberDisplayRows(rows), [rows]);

  const handleFilterChange = useCallback((type: SyncFilterType) => {
    setFilterType(type);
    setCurrentPage(1);
  }, []);

  return (
    <section className="flex w-250 flex-col gap-10">
      <StatusCardsSection cards={cards} />
      <UsersStatusSection
        total={total}
        displayRows={displayRows}
        filterType={filterType}
        onFilterChange={handleFilterChange}
        currentPage={currentPage}
        onPageChange={setCurrentPage}
      />
    </section>
  );
};

export default IntegrationsSection;
