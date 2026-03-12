'use client';

import { useMemo, useState } from 'react';
import { toast } from 'sonner';

import Cancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import type { IntegrationService } from '@/shared/types/integrationService';
import { cn } from '@/shared/utils/cn';

import { getMockTargets } from '../../../constants/mockSyncData';
import type { SyncConnector, SyncTargetItem } from '../../../types/sync';
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
}

/** 임베딩 모달 (셸) */
const EmbeddingModal = ({ open, onOpenChange, service, serviceName }: EmbeddingModalProps) => {
  const [selectedPeriod, setSelectedPeriod] = useState<string>('1개월');
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const selectedScopeId = 'mock-scope-id';

  const targets = useMemo(() => getMockTargets(service as SyncConnector), [service]);

  const itemLabel = getItemLabel(service);
  const isSubmitDisabled = selectedItems.size === 0;

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

  const handleSubmit = () => {
    const syncDays = PERIOD_TO_DAYS[selectedPeriod] ?? 30;
    const selectedTargets = targets.filter((t: SyncTargetItem) => selectedItems.has(t.target_id));

    console.log('[임베딩 요청]', {
      connector: service,
      scope_id: selectedScopeId,
      target_ids: selectedTargets.map((t: SyncTargetItem) => t.target_id),
      sync_days: syncDays,
    });

    toast('임베딩이 시작되었습니다.', {
      description: '준비가 끝나면 즉시 알려드릴게요.',
    });
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

            <EmbeddingModalContent
              targets={targets}
              selectedItems={selectedItems}
              onToggleItem={toggleItem}
            />
          </div>
        </div>

        {/* 푸터 */}
        <div className="flex h-9 items-start justify-end gap-3 px-6">
          <Button variant="capsule-outline-mono" size="md" onClick={handleClose}>
            취소
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="md"
            disabled={isSubmitDisabled}
            onClick={handleSubmit}
          >
            임베딩하기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EmbeddingModal;
