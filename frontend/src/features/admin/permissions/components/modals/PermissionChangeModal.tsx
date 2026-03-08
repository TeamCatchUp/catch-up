'use client';

import { useMemo, useState } from 'react';

import Cancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';

import { PERMISSION_CHANGE_REASONS } from '../../constants/permissionsConfig';
import type { PermissionMember } from '../../types/adminPermission';

interface PermissionChangeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  members: PermissionMember[];
  initialMemberId: number | null;
  isSubmitting: boolean;
  errorMessage?: string;
  onSubmit: (userId: number) => void;
}

/** 권한 변경 모달 */
const PermissionChangeModal = ({
  open,
  onOpenChange,
  members,
  initialMemberId,
  isSubmitting,
  errorMessage,
  onSubmit,
}: PermissionChangeModalProps) => {
  const [memberId, setMemberId] = useState<number | null>(initialMemberId);
  const [selectedReason, setSelectedReason] = useState<string>(PERMISSION_CHANGE_REASONS[0]);
  const [customReason, setCustomReason] = useState('');

  const finalReason = useMemo(() => {
    if (selectedReason !== '직접 입력') return selectedReason;
    return customReason.trim();
  }, [customReason, selectedReason]);

  const isSubmitDisabled = !memberId || !finalReason || isSubmitting;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="border-edge-neutral shadow-modal max-w-[400px] gap-2 rounded-2xl border bg-fill-normal px-5 pt-3 pb-4"
      >
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-content-normal">Admin 권한 부여</DialogTitle>
          <button type="button" onClick={() => onOpenChange(false)} className="cursor-pointer" aria-label="닫기">
            <Cancel className="size-5 text-content-alternative" />
          </button>
        </div>

        <div className="border-edge-neutral flex w-[360px] flex-col gap-4 border-t pt-4">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1">
              <span className="text-body-small text-content-normal">부여할 멤버</span>
              <span className="size-1.25 rounded-full bg-red-50" />
            </div>

            <Select value={memberId != null ? String(memberId) : ''} onValueChange={(v) => setMemberId(Number(v))}>
              <SelectTrigger className="h-[46px]">
                <SelectValue placeholder="멤버 선택" />
              </SelectTrigger>
              <SelectContent>
                {members.map((member) => (
                  <SelectItem key={member.id} value={String(member.id)}>
                    {member.name} ({member.department})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-body-small text-content-normal">권한 부여 사유를 선택해주세요.</span>
              <span className="size-1.25 rounded-full bg-red-50" />
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
                            <div className="border-blue-40 size-[18px] rounded-full border-[1.5px]" />
                            <div className="bg-blue-40 absolute size-2.5 rounded-full" />
                          </>
                        ) : (
                          <div className="border-edge-strong size-[18px] rounded-full border-[1.5px]" />
                        )}
                      </div>
                      <span className="text-body-small text-content-alternative">{reason}</span>
                    </button>

                    {isCustom && isSelected && (
                      <Input
                        autoFocus
                        value={customReason}
                        onChange={(event) => setCustomReason(event.target.value)}
                        placeholder="사유를 입력해주세요."
                        className="ml-9 h-10"
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {errorMessage && <p className="text-label-xsmall text-red-50">{errorMessage}</p>}
        </div>

        <div className="mt-1 flex w-[360px] justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="md" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            취소
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="md"
            disabled={isSubmitDisabled}
            onClick={() => memberId != null && onSubmit(memberId)}
          >
            권한 부여
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default PermissionChangeModal;
