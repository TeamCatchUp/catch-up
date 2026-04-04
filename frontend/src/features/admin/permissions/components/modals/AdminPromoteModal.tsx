'use client';

import { useMemo, useState } from 'react';

import Cancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';

import { PERMISSION_CHANGE_REASONS } from '../../constants/permissionsConfig';
import type { PermissionMember } from '../../types/adminPermissionModel';

interface AdminPromoteModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  member: PermissionMember | null;
  isSubmitting: boolean;
  errorMessage?: string;
  onSubmit: (userId: number, reason: string) => void;
}

/** Admin 권한 부여 모달 */
const AdminPromoteModal = ({
  open,
  onOpenChange,
  member,
  isSubmitting,
  errorMessage,
  onSubmit,
}: AdminPromoteModalProps) => {
  const [selectedReason, setSelectedReason] = useState<string>(PERMISSION_CHANGE_REASONS[0]);
  const [customReason, setCustomReason] = useState('');

  const finalReason = useMemo(() => {
    if (selectedReason !== '직접 입력') return selectedReason;
    return customReason.trim();
  }, [customReason, selectedReason]);

  const isSubmitDisabled = !member || !finalReason || isSubmitting;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="border-edge-neutral shadow-modal bg-fill-normal max-w-100 gap-2 rounded-2xl border px-5 pt-3 pb-4"
      >
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-content-normal">Admin 권한 부여</DialogTitle>
          <button type="button" onClick={() => onOpenChange(false)} className="cursor-pointer" aria-label="닫기">
            <Cancel className="text-content-alternative size-5" />
          </button>
        </div>

        <div className="border-edge-neutral flex w-90 flex-col gap-4 border-t pt-4">
          {/* 권한 정보 테이블 */}
          <div className="flex flex-col gap-1.5">
            <span className="text-body-small text-content-normal">권한 정보</span>
            <div className="border-edge-normal flex h-12 items-center border-y">
              <div className="bg-fill-primary-assistive flex h-full w-36.25 items-center px-4">
                <span className="text-body-small text-content-neutral">부여할 멤버</span>
              </div>
              <div className="flex flex-1 items-center px-4">
                <span className="text-body-small text-content-neutral truncate">
                  {member ? `${member.name}(${member.department})` : ''}
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-body-small text-content-normal">권한 부여 사유를 선택해주세요.</span>
              <span className="bg-status-destructive size-1.25 rounded-full" />
            </div>

            <div className="border-edge-assistive flex flex-col gap-4 rounded-xl border px-4 py-4">
              {PERMISSION_CHANGE_REASONS.map((reason) => {
                const isSelected = selectedReason === reason;
                const isCustom = reason === '직접 입력';

                return (
                  <div key={reason} className="flex flex-col gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedReason(reason)}
                      className="flex w-full cursor-pointer items-center gap-3 text-left"
                    >
                      <div className="relative flex size-6 shrink-0 items-center justify-center">
                        {isSelected ? (
                          <>
                            <div className="border-icon-primary size-4.5 rounded-full border-[1.5px]" />
                            <div className="bg-icon-primary absolute size-2.5 rounded-full" />
                          </>
                        ) : (
                          <div className="border-edge-strong size-4.5 rounded-full border-[1.5px]" />
                        )}
                      </div>
                      <span className="text-body-small text-content-alternative">{reason}</span>
                    </button>

                    {isCustom && isSelected && (
                      <div className="pl-9">
                        <Input
                          autoFocus
                          value={customReason}
                          onChange={(event) => setCustomReason(event.target.value)}
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

          {errorMessage && <p className="text-label-xsmall text-status-destructive">{errorMessage}</p>}
        </div>

        <div className="mt-1 flex w-90 justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="md" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            취소
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="md"
            disabled={isSubmitDisabled}
            onClick={() => member && onSubmit(member.id, finalReason)}
          >
            권한 부여
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AdminPromoteModal;
