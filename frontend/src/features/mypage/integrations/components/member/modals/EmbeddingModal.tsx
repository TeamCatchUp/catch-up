'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import Cancel from '@/public/icons/icon/cancel.svg';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import { Skeleton } from '@/shared/components/ui/skeleton';
import type { IntegrationService } from '@/shared/types/integrationService';
import { cn } from '@/shared/utils/cn';

import { useScopeId } from '../../../hooks/useScopeId';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import type { FullSyncRequest, SyncAcceptedResponse, SyncConnector } from '../../../types/sync';
import EmbeddingModalContent from './EmbeddingModalContent';

const PERIOD_OPTIONS = ['1개월', '3개월', '6개월', '1년', '3년'] as const;

const PERIOD_TO_DAYS: Record<string, number> = {
  '1개월': 30,
  '3개월': 90,
  '6개월': 180,
  '1년': 365,
  '3년': 1095,
};

/** 서비스별 항목 용어 */
const getItemLabel = (service: IntegrationService) => {
  switch (service) {
    case 'github':
      return 'Repository';
    case 'slack':
      return 'Channel';
    default:
      return 'Space';
  }
};

interface EmbeddingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  service: IntegrationService;
  serviceName: string;
  onJobStart?: (jobId: string, connector: SyncConnector) => void;
}

/** 임베딩 모달 (셸) */
const EmbeddingModal = ({ open, onOpenChange, service, serviceName, onJobStart }: EmbeddingModalProps) => {
  const [selectedPeriod, setSelectedPeriod] = useState<string>('1개월');
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());

  const connector = service as SyncConnector;
  const { scopeId, isLoading: isScopeLoading } = useScopeId(service);

  const { data: targetsData, isLoading: isTargetsLoading } = useQuery({
    ...adminConnectorQueries.syncTargets(connector, scopeId ?? ''),
    enabled: !!scopeId,
  });

  const targets = useMemo(() => targetsData?.targets ?? [], [targetsData]);

  const syncMutation = useMutation({
    mutationKey: ['admin', 'sync', 'full'] as const,
    mutationFn: (body: FullSyncRequest) => api.post<SyncAcceptedResponse>(API.sync.full, body),
  });

  const itemLabel = getItemLabel(service);
  const isSubmitDisabled = selectedItems.size === 0 || syncMutation.isPending;
  const noScope = !isScopeLoading && !scopeId;

  const toggleItem = (targetId: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(targetId)) next.delete(targetId);
      else next.add(targetId);
      return next;
    });
  };

  const resetFormState = () => {
    setSelectedPeriod('1개월');
    setSelectedItems(new Set());
  };

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) resetFormState();
    onOpenChange(nextOpen);
  };

  const handleClose = () => handleDialogOpenChange(false);

  const handleSubmit = async () => {
    if (!scopeId) return;

    const syncDays = PERIOD_TO_DAYS[selectedPeriod] ?? 30;
    const targetIds = targets
      .filter((t) => selectedItems.has(t.target_id))
      .map((t) => t.target_id);

    try {
      const result = await syncMutation.mutateAsync({
        connector,
        scope_id: scopeId,
        target_ids: targetIds,
        sync_days: syncDays,
      });

      const response = result.data;

      switch (response.status) {
        case 'accepted':
          toast('임베딩이 시작되었습니다.', {
            description: '준비가 끝나면 즉시 알려드릴게요.',
          });
          if (response.job_id) onJobStart?.(response.job_id, connector);
          break;
        case 'conflict':
          toast.warning('이미 진행 중인 임베딩이 있습니다.');
          if (response.job_id) onJobStart?.(response.job_id, connector);
          break;
        case 'no_events':
          toast.info('임베딩할 대상이 없습니다.');
          break;
        case 'failed':
          toast.error(response.message ?? '임베딩 요청에 실패했습니다.');
          break;
      }
    } catch {
      toast.error('임베딩 요청 중 오류가 발생했습니다.');
    }

    handleClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent
        hideClose
        className="border-edge-normal shadow-modal w-140 gap-4 rounded-3xl border bg-fill-normal p-0 py-5"
      >
        {/* 헤더 */}
        <div className="flex h-9 items-center gap-3 px-6">
          <DialogTitle className="text-heading-large min-w-0 flex-1 text-content-normal">
            임베딩 할 {serviceName} {itemLabel} 선택하기
          </DialogTitle>
          <button
            type="button"
            onClick={handleClose}
            className="flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-lg"
            aria-label="닫기"
          >
            <Cancel className="size-6 text-content-alternative" />
          </button>
        </div>

        {/* 바디 */}
        <div className="flex max-h-152 min-h-102 flex-col gap-6 overflow-y-auto overflow-x-clip border-t border-edge-assistive px-6 pt-6">
          {noScope ? (
            <div className="flex flex-1 items-center justify-center">
              <span className="text-body-small text-content-assistive">
                연동된 {serviceName}이(가) 없습니다. 먼저 연동을 완료해주세요.
              </span>
            </div>
          ) : (
            <>
              {/* 기간 선택 */}
              <div className="flex flex-col gap-2.5">
                <div className="flex items-center gap-1">
                  <span className="text-body-medium text-content-strong">
                    임베딩 할 데이터의 기간을 선택해 주세요.
                  </span>
                  <span className="block size-1.25 shrink-0 rounded-full bg-accent-red-orange" />
                </div>
                <div className="flex gap-2">
                  {PERIOD_OPTIONS.map((period) => (
                    <button
                      key={period}
                      type="button"
                      onClick={() => setSelectedPeriod(period)}
                      className={cn(
                        'text-body-small h-9 cursor-pointer rounded-full px-3',
                        selectedPeriod === period
                          ? 'bg-accent-black-lighten text-content-inverse'
                          : 'border border-edge-neutral bg-fill-normal text-content-neutral',
                      )}
                    >
                      {period}
                    </button>
                  ))}
                </div>
              </div>

              {/* 항목 선택 */}
              <div className="flex flex-col gap-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    <span className="text-body-medium text-content-strong">
                      {itemLabel}를 선택해주세요.
                    </span>
                    <span className="block size-1.25 shrink-0 rounded-full bg-accent-red-orange" />
                  </div>
                  {selectedItems.size > 0 && (
                    <span className="text-body-small text-content-primary">
                      {selectedItems.size}개 선택됨
                    </span>
                  )}
                </div>

                {isScopeLoading || isTargetsLoading ? (
                  <div className="overflow-clip rounded-xl border border-edge-assistive">
                    <div className="flex flex-col">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-5 border-b border-edge-assistive px-5 py-3 last:border-b-0"
                        >
                          <Skeleton className="h-4 flex-1" />
                          <Skeleton className="size-6 shrink-0 rounded" />
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <EmbeddingModalContent
                    targets={targets}
                    selectedItems={selectedItems}
                    onToggleItem={toggleItem}
                  />
                )}
              </div>
            </>
          )}
        </div>

        {/* 푸터 */}
        <div className="flex h-9 items-start justify-end gap-3 px-6">
          <Button variant="capsule-outline-mono" size="md" onClick={handleClose}>
            취소
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="md"
            disabled={isSubmitDisabled || noScope}
            onClick={handleSubmit}
          >
            {syncMutation.isPending ? '요청 중...' : '임베딩하기'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EmbeddingModal;
