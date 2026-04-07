import { useState } from 'react';

import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconErrorFilled from '@/public/icons/icon/error_filled.svg';
import { cn } from '@/shared/utils/cn';

import type { GapSummary } from '../../../hooks/useEmbeddingGaps';
import { useSyncRecordRetry } from '../../../queries/syncRecords.mutations';
import type { AdminConnectorTargetRangeResponse, SyncConnector } from '../../../types/syncModel';
import { formatHistoryDate, RESOURCE_ICONS } from '../../../utils/embeddingUtils';
import EmbeddingRetryModal from '../modals/EmbeddingRetryModal';

type HistoryFilter = 'all' | 'success' | 'failed';

interface EmbeddingHistoryCardProps {
  items: AdminConnectorTargetRangeResponse[];
  connector: SyncConnector;
  isInitialLoading?: boolean;
  gapByTargetId?: Map<string, GapSummary>;
}

export default function EmbeddingHistoryCard({
  items,
  connector,
  isInitialLoading,
  gapByTargetId,
}: EmbeddingHistoryCardProps) {
  const [filter, setFilter] = useState<HistoryFilter>('all');
  const [retryTarget, setRetryTarget] = useState<AdminConnectorTargetRangeResponse | null>(null);

  const retryMutation = useSyncRecordRetry();
  const ResourceIcon = RESOURCE_ICONS[connector];

  const failedItems = items.filter((item) => item.sync_status === 'failed');
  const successItems = items.filter((item) => item.sync_status === 'success');

  const filteredFailed = filter === 'success' ? [] : failedItems;
  const filteredSuccess = filter === 'failed' ? [] : successItems;
  const isEmpty = filteredFailed.length === 0 && filteredSuccess.length === 0;

  const filterOptions: { value: HistoryFilter; label: string; count?: number; hasRedTag?: boolean }[] = [
    { value: 'all', label: '전체' },
    { value: 'success', label: '성공', count: successItems.length },
    { value: 'failed', label: '실패', count: failedItems.length, hasRedTag: failedItems.length > 0 },
  ];

  const getGap = (targetId: string): GapSummary | undefined => gapByTargetId?.get(targetId);

  const handleRetryConfirm = () => {
    if (!retryTarget) return;
    const gap = getGap(retryTarget.target_id);
    if (!gap) return;

    retryMutation.mutate(
      {
        event_id: gap.eventId,
        records: gap.records
          .filter((r) => r.missing_count > 0)
          .map((r) => ({
            record_type: r.record_type,
            record_ids: r.missing_ids,
          })),
      },
      {
        onSuccess: () => {
          setRetryTarget(null);
        },
      },
    );
  };

  // 모달에 전달할 gap 기반 데이터
  const retryGap = retryTarget ? getGap(retryTarget.target_id) : undefined;
  const modalTotalCount = retryGap ? retryGap.totalExpected : 0;
  const modalSuccessCount = retryGap ? retryGap.totalStored : 0;
  const modalFailedCount = retryGap ? retryGap.totalMissing : 0;

  return (
    <>
      <div className="border-edge-assistive bg-fill-normal flex flex-col gap-4 overflow-clip rounded-2xl border py-4">
        {/* 헤더: 타이틀 + 필터 칩 */}
        <div className="flex items-center justify-between px-4">
          <span className="text-body-small text-content-normal">임베딩 히스토리</span>
          <div className="flex items-center gap-0.5">
            {filterOptions.map(({ value, label, count, hasRedTag }) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={cn(
                  'text-body-small relative h-9 cursor-pointer rounded-full px-3',
                  filter === value ? 'border-edge-strong bg-fill-normal border' : 'text-content-alternative',
                )}
              >
                {label}
                {count !== undefined && ` ${count}`}
                {hasRedTag && (
                  <span className="bg-status-destructive absolute top-1.5 right-1.5 size-1.5 rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* 빈 상태 */}
        {isEmpty && (
          <div className="flex h-14 items-center justify-center px-4">
            <span className="text-body-small text-content-assistive">
              {isInitialLoading
                ? '임베딩 상태를 불러오는 중...'
                : filter === 'success'
                  ? '성공한 항목이 없습니다.'
                  : filter === 'failed'
                    ? '실패한 항목이 없습니다.'
                    : '임베딩 히스토리가 없습니다.'}
            </span>
          </div>
        )}

        {/* 실패 섹션 */}
        {filteredFailed.length > 0 && (
          <div className="flex flex-col gap-1">
            {/* 섹션 헤더 */}
            <div className="flex items-center gap-6 px-4">
              <div className="flex items-center gap-1">
                <span className="text-body-xsmall text-status-destructive">임베딩 실패</span>
                <IconErrorFilled className="text-status-destructive size-4.5" />
              </div>
              <div className="border-edge-assistive flex-1 border-t" />
            </div>

            {/* 실패 아이템 리스트 */}
            <div className="flex flex-col">
              {filteredFailed.map((item) => {
                const gap = getGap(item.target_id);
                return (
                  <div
                    key={`${item.scope_id}-${item.target_id}`}
                    className="border-edge-assistive flex h-14 shrink-0 items-center gap-4 border-b px-4 last:border-b-0"
                  >
                    <div className="border-edge-normal bg-fill-normal/75 flex shrink-0 items-center justify-center overflow-hidden rounded-full border p-1.5">
                      <ResourceIcon className="size-5" />
                    </div>
                    <span className="text-body-small text-content-normal flex-1 truncate">{item.target_name}</span>
                    <div className="flex shrink-0 items-center gap-4">
                      <div className="flex items-center gap-1.5">
                        <span className="text-label-xsmall text-content-alternative whitespace-nowrap">
                          {formatHistoryDate(item.last_failed_at ?? '')}
                        </span>
                        <div className="border-edge-neutral h-3.75 border-r" />
                        <span className="text-label-xsmall text-content-alternative whitespace-nowrap">
                          {gap ? `${gap.totalMissing}건 실패` : '-'}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setRetryTarget(item)}
                        disabled={!gap}
                        className="border-edge-neutral bg-fill-normal text-body-xsmall text-content-normal flex h-7.5 cursor-pointer items-center justify-center rounded-lg border px-2 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        재시도
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 성공 섹션 */}
        {filteredSuccess.length > 0 && (
          <div className="flex flex-col gap-1">
            {/* 섹션 헤더 */}
            <div className="flex items-center gap-6 px-4">
              <div className="flex items-center gap-1">
                <span className="text-body-xsmall text-status-positive">임베딩 성공</span>
                <IconCheckCircleFilled className="text-status-positive size-4.5" />
              </div>
              <div className="border-edge-assistive flex-1 border-t" />
            </div>

            {/* 성공 아이템 리스트 */}
            <div className="flex flex-col">
              {filteredSuccess.map((item) => (
                <div
                  key={`${item.scope_id}-${item.target_id}`}
                  className="border-edge-assistive flex h-14 shrink-0 items-center gap-4 px-4"
                >
                  <div className="border-edge-normal bg-fill-normal/75 flex shrink-0 items-center justify-center overflow-hidden rounded-full border p-1.5">
                    <ResourceIcon className="size-5" />
                  </div>
                  <div className="border-edge-assistive flex flex-1 items-center gap-5 border-b py-4">
                    <span className="text-body-small text-content-normal flex-1 truncate">{item.target_name}</span>
                    <span className="text-label-xsmall text-content-alternative shrink-0 whitespace-nowrap">
                      {formatHistoryDate(item.last_succeeded_at ?? '')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 재시도 모달 */}
      <EmbeddingRetryModal
        open={!!retryTarget}
        onOpenChange={(open) => {
          if (!open && !retryMutation.isPending) setRetryTarget(null);
        }}
        targetName={retryTarget?.target_name ?? ''}
        totalCount={modalTotalCount}
        successCount={modalSuccessCount}
        failedCount={modalFailedCount}
        retryAttempt={retryGap?.attempt ?? 0}
        isLoading={retryMutation.isPending}
        onConfirm={handleRetryConfirm}
      />
    </>
  );
}
