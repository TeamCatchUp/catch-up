'use client';

import { type ReactNode, useState } from 'react';

import Cancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';

interface ReasonPopoverProps {
  trigger: ReactNode;
  title: string;
  reasonLabel: string;
  reasons: readonly string[];
  /** 반려 사유 전용: 신청 사유 표시 */
  requestReason?: string;
  onSave: (reason: string) => void;
}

/** 사유 선택 팝오버 (반려 / 비활성화 공통) */
const ReasonPopover = ({
  trigger,
  title,
  reasonLabel,
  reasons,
  requestReason,
  onSave,
}: ReasonPopoverProps) => {
  const [open, setOpen] = useState(false);
  const [selectedReason, setSelectedReason] = useState<string | null>(null);

  const handleSave = () => {
    if (!selectedReason) return;
    onSave(selectedReason);
    setOpen(false);
    setSelectedReason(null);
  };

  const handleClose = () => {
    setOpen(false);
    setSelectedReason(null);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={6}
        className="shadow-modal w-100 gap-2 px-5 pb-4 pt-3"
      >
        {/* 헤더 */}
        <div className="flex h-9 items-center justify-between">
          <h3 className="text-heading-medium text-gray-80">{title}</h3>
          <button type="button" onClick={handleClose} className="cursor-pointer p-0.5">
            <Cancel className="text-gray-50 size-6" />
          </button>
        </div>

        {/* 구분선 + 내용 */}
        <div className="border-neutral-3 flex flex-col gap-4 border-t pt-4">
          {/* 신청 사유 (반려 전용) */}
          {requestReason && (
            <div className="bg-neutral-1 border-neutral-2 text-body-small flex gap-3 rounded-lg border px-3 py-2">
              <span className="shrink-0 text-gray-50">신청 사유</span>
              <span className="text-gray-60 truncate">{requestReason}</span>
            </div>
          )}

          {/* 사유 선택 */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-body-small text-gray-80">{reasonLabel}</span>
              <span className="bg-red-50 size-1.25 rounded-full" />
            </div>

            <div className="border-neutral-2 flex flex-col gap-4 rounded-xl border px-4 py-4">
              {reasons.map((reason) => {
                const isSelected = selectedReason === reason;
                return (
                  <button
                    key={reason}
                    type="button"
                    onClick={() => setSelectedReason(reason)}
                    className="flex cursor-pointer items-center gap-3"
                  >
                    <div className="relative flex size-6 shrink-0 items-center justify-center">
                      {isSelected ? (
                        <>
                          <div className="border-blue-40 size-[18px] rounded-full border-[1.5px]" />
                          <div className="bg-blue-40 absolute size-2.5 rounded-full" />
                        </>
                      ) : (
                        <div className="border-neutral-5 size-[18px] rounded-full border-[1.5px]" />
                      )}
                    </div>
                    <span className="text-body-small text-gray-60">{reason}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* 하단 버튼 */}
        <div className="flex justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="sm" onClick={handleClose}>
            취소
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="sm"
            onClick={handleSave}
            disabled={!selectedReason}
          >
            저장
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default ReasonPopover;
