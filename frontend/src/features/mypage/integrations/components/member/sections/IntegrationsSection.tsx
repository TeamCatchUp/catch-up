'use client';

import { useCallback, useMemo, useState } from 'react';

import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';

import { INTEGRATION_ACCOUNTS } from '../../../constants/integrations';
import { useEmbeddingJobs } from '../../../hooks/useEmbeddingJobs';
import { useMemberIntegrationViewModel } from '../../../hooks/useMemberIntegrationViewModel';
import type { SyncFilterType } from '../../../types/api';
import type { EmbeddingButtonState, SyncConnector } from '../../../types/sync';
import { buildMemberDisplayRows } from '../../../utils/memberDisplay';
import EmbeddingProgressPanel from '../panels/EmbeddingProgressPanel';
import StatusCardsSection from './StatusCardsSection';
import UsersStatusSection from './UsersStatusSection';

const PAGE_SIZE = 10;
const CONNECTOR_ORDER: SyncConnector[] = ['jira', 'github', 'slack', 'confluence'];

/** 관리자 이용자 연동 탭 섹션 */
const IntegrationsSection = () => {
  const [filterType, setFilterType] = useState<SyncFilterType>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [completionInfo, setCompletionInfo] = useState<{
    connector: SyncConnector;
    successCount: number;
    totalCount: number;
  } | null>(null);

  const { cards, rows, total } = useMemberIntegrationViewModel({
    filterType,
    page: currentPage,
    size: PAGE_SIZE,
  });

  const { buttonStates, progresses, handleJobStart } = useEmbeddingJobs();

  // in_progress → completed 전환 감지 → 결과 모달 표시
  const [lastSeenStates, setLastSeenStates] = useState('');
  const currentStates = CONNECTOR_ORDER.map((c) => buttonStates[c]).join(',');

  if (currentStates !== lastSeenStates) {
    const prev = lastSeenStates.split(',') as EmbeddingButtonState[];
    for (let i = 0; i < CONNECTOR_ORDER.length; i++) {
      const connector = CONNECTOR_ORDER[i];
      if (buttonStates[connector] === 'completed' && prev[i] === 'in_progress') {
        const progress = progresses.find((p) => p.connector === connector);
        const successCount = progress?.items.filter((item) => item.status === 'success').length ?? 0;
        const totalCount = progress?.items.length ?? 0;
        setCompletionInfo({ connector, successCount, totalCount });
        break;
      }
    }
    setLastSeenStates(currentStates);
  }

  const completedServiceName =
    INTEGRATION_ACCOUNTS.find((a) => a.service === completionInfo?.connector)?.name ?? '';

  const displayRows = useMemo(() => buildMemberDisplayRows(rows), [rows]);

  const handleFilterChange = useCallback((type: SyncFilterType) => {
    setFilterType(type);
    setCurrentPage(1);
  }, []);

  return (
    <section className="flex w-250 flex-col gap-8">
      <div className="flex flex-col gap-3">
        <StatusCardsSection cards={cards} buttonStates={buttonStates} onJobStart={handleJobStart} />
        <EmbeddingProgressPanel progresses={progresses} buttonStates={buttonStates} />
      </div>
      <UsersStatusSection
        total={total}
        displayRows={displayRows}
        filterType={filterType}
        onFilterChange={handleFilterChange}
        currentPage={currentPage}
        onPageChange={setCurrentPage}
      />

      <ConfirmDialog
        open={!!completionInfo}
        onOpenChange={(open) => {
          if (!open) setCompletionInfo(null);
        }}
        title={
          completionInfo && completionInfo.successCount < completionInfo.totalCount
            ? '임베딩에 실패했어요'
            : '임베딩이 완료되었어요!'
        }
        description={
          completionInfo
            ? completionInfo.successCount === completionInfo.totalCount
              ? `${completedServiceName} ${completionInfo.totalCount}개 중 ${completionInfo.successCount}개 성공\n이제 Catch Up에서 ${completedServiceName} 정보를 검색할 수 있어요.`
              : `${completedServiceName} ${completionInfo.totalCount}개 중 ${completionInfo.successCount}개 성공`
            : ''
        }
        confirmLabel="확인"
        variant="mono"
        hideCancel
        onConfirm={() => setCompletionInfo(null)}
      />
    </section>
  );
};

export default IntegrationsSection;
