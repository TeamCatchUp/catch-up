'use client';

import { useState } from 'react';
import { toast } from 'sonner';

import Cancel from '@/public/icons/icon/cancel.svg';
import CheckboxChecked from '@/public/icons/icon/checkbox_checked.svg';
import CheckboxUnchecked from '@/public/icons/icon/checkbox_unchecked.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import type { IntegrationService } from '@/shared/types/integrationService';

const PERIOD_OPTIONS = ['1개월', '3개월', '6개월', '1년', '3년'] as const;

/** 서비스별 항목 용어 */
const getItemLabel = (service: IntegrationService) => (service === 'github' ? 'Repository' : 'Space');

/** 임시 Mock 데이터 (추후 API 연동) */
const MOCK_ITEMS = [
  { id: '1', name: 'Project Alpha' },
  { id: '2', name: 'Project Beta' },
  { id: '3', name: 'Project Gamma' },
  { id: '4', name: 'Project Delta' },
  { id: '5', name: 'Project Epsilon' },
  { id: '6', name: 'Project Zeta' },
  { id: '7', name: 'Project Eta' },
];

interface EmbeddingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  service: IntegrationService;
  serviceName: string;
}

/** 임베딩 모달 */
const EmbeddingModal = ({ open, onOpenChange, service, serviceName }: EmbeddingModalProps) => {
  const [selectedPeriod, setSelectedPeriod] = useState<string>('1개월');
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());

  const itemLabel = getItemLabel(service);
  const isSubmitDisabled = selectedItems.size === 0;

  const toggleItem = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
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

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent
        hideClose
        className="border-neutral-3 shadow-modal max-w-[400px] gap-2 rounded-2xl border bg-white px-5 pt-3 pb-4"
      >
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-gray-80">
            임베딩 할 {serviceName} {itemLabel} 선택하기
          </DialogTitle>
          <button type="button" onClick={handleClose} className="cursor-pointer" aria-label="닫기">
            <Cancel className="size-5 text-gray-50" />
          </button>
        </div>

        <div className="border-neutral-3 w-full border-t pt-4">
          <div className="flex flex-col gap-4">
            {/* 기간 선택 */}
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center gap-1">
                <span className="text-body-small text-gray-90">등록 사유를 선택해주세요.</span>
                <span className="block size-[5px] shrink-0 rounded-full bg-red-50" />
              </div>
              <div className="flex gap-2">
                {PERIOD_OPTIONS.map((period) => (
                  <button
                    key={period}
                    type="button"
                    onClick={() => setSelectedPeriod(period)}
                    className={`text-body-small h-9 cursor-pointer rounded-full px-3 ${
                      selectedPeriod === period ? 'bg-gray-80 text-white' : 'border-neutral-3 text-gray-60 border'
                    }`}
                  >
                    {period}
                  </button>
                ))}
              </div>
            </div>

            {/* Space/Repository 선택 */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                <span className="text-body-small text-gray-90">{itemLabel}를 선택해주세요.</span>
                <span className="block size-[5px] shrink-0 rounded-full bg-red-50" />
              </div>
              <div className="thin-scrollbar border-neutral-2 bg-neutral-1 flex h-[200px] flex-col gap-2.5 overflow-y-auto rounded-xl border p-3">
                {MOCK_ITEMS.map((item) => {
                  const checked = selectedItems.has(item.id);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => toggleItem(item.id)}
                      className="flex w-full cursor-pointer items-center gap-3"
                    >
                      <span className="text-body-small text-gray-60 min-w-0 flex-1 truncate text-left">
                        {item.name}
                      </span>
                      {checked ? (
                        <CheckboxChecked className="size-6 shrink-0 text-blue-50" />
                      ) : (
                        <CheckboxUnchecked className="text-gray-30 size-6 shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-1 flex h-9 w-full items-start justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="md" onClick={handleClose}>
            취소
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="md"
            disabled={isSubmitDisabled}
            onClick={() => {
              toast('잠시만 기다려주세요', {
                description: '임베딩을 진행하고 있습니다. 준비가 끝나면 즉시 알려드릴게요.',
              });
              handleClose();
            }}
          >
            임베딩하기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EmbeddingModal;
