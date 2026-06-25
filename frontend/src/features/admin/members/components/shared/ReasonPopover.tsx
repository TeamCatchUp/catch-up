'use client';

import { useState } from 'react';

import Cancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';

interface ReasonDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  reasonLabel: string;
  reasons: readonly string[];
  /** 반려 사유 전용: 신청 사유 표시 */
  requestReason?: string;
  onSave: (reason: string) => void;
}

/** 사유 선택 모달 (반려 / 비활성화 공통) */
export default function ReasonDialog({
  open,
  onOpenChange,
  title,
  reasonLabel,
  reasons,
  requestReason,
  onSave,
}: ReasonDialogProps) {
  const [selectedReason, setSelectedReason] = useState<string | null>(null);
  const [customReason, setCustomReason] = useState('');

  const CUSTOM_REASON_KEY = '직접 입력';
  const isCustom = selectedReason === CUSTOM_REASON_KEY;

  const handleSave = () => {
    if (!selectedReason) return;
    onSave(isCustom ? customReason : selectedReason);
    onOpenChange(false);
    setSelectedReason(null);
    setCustomReason('');
  };

  const handleClose = () => {
    onOpenChange(false);
    setSelectedReason(null);
    setCustomReason('');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="border-line-normal-neutral shadow-modal bg-fill-normal-normal max-w-100 gap-2 rounded-2xl border px-5 pt-3 pb-4"
      >
        {/* 헤더 */}
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-text-normal-normal">{title}</DialogTitle>
          <button type="button" onClick={handleClose} className="cursor-pointer p-0.5" aria-label="닫기">
            <Cancel className="text-text-normal-alternative size-5" />
          </button>
        </div>

        {/* 구분선 + 내용 */}
        <div className="border-line-normal-neutral flex flex-col gap-4 border-t pt-4">
          {/* 신청 사유 (반려 전용) */}
          {requestReason && (
            <div className="bg-fill-normal-strong border-line-normal-assistive text-body-small flex gap-3 rounded-lg border px-3 py-2">
              <span className="text-text-normal-alternative shrink-0">신청 사유</span>
              <span className="text-text-normal-alternative truncate">{requestReason}</span>
            </div>
          )}

          {/* 사유 선택 */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-body-small text-text-normal-normal">{reasonLabel}</span>
              <span className="bg-status-destructive size-1.25 rounded-full" />
            </div>

            <div className="border-line-normal-assistive flex flex-col gap-4 rounded-xl border px-4 py-4">
              {reasons.map((reason) => {
                const isSelected = selectedReason === reason;
                return (
                  <div key={reason} className="flex flex-col gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedReason(reason)}
                      className="flex w-full cursor-pointer items-center gap-3"
                    >
                      <div className="relative flex size-6 shrink-0 items-center justify-center">
                        {isSelected ? (
                          <>
                            <div className="border-icon-primary size-4.5 rounded-full border-[1.5px]" />
                            <div className="bg-icon-primary absolute size-2.5 rounded-full" />
                          </>
                        ) : (
                          <div className="border-line-normal-strong size-4.5 rounded-full border-[1.5px]" />
                        )}
                      </div>
                      <span className="text-body-small text-text-normal-alternative">{reason}</span>
                    </button>
                    {reason === CUSTOM_REASON_KEY && isCustom && (
                      <div className="pl-9">
                        <Input
                          autoFocus
                          value={customReason}
                          onChange={(e) => setCustomReason(e.target.value)}
                          placeholder="사유를 입력해주세요."
                          className="h-10"
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 하단 버튼 */}
        <div className="flex justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="md" onClick={handleClose}>
            취소
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="md"
            onClick={handleSave}
            disabled={!selectedReason || (isCustom && !customReason.trim())}
          >
            저장
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
