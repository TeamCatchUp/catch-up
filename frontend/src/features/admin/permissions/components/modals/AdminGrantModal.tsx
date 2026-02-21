'use client';

import { useState } from 'react';

import Cancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';

import type { AssignAdminPayload, PermissionMember } from '../../types/adminPermission';

interface AdminGrantModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  members: PermissionMember[];
  initialMemberId: string;
  initialReason: string;
  isSubmitting: boolean;
  errorMessage?: string;
  onSubmit: (payload: AssignAdminPayload) => void;
}

/** Admin 권한 부여 모달 */
const AdminGrantModal = ({
  open,
  onOpenChange,
  members,
  initialMemberId,
  initialReason,
  isSubmitting,
  errorMessage,
  onSubmit,
}: AdminGrantModalProps) => {
  const [memberId, setMemberId] = useState(initialMemberId);
  const [reason, setReason] = useState(initialReason);

  const isSubmitDisabled = !memberId || !reason.trim() || isSubmitting;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="border-neutral-3 shadow-modal max-w-[400px] gap-2 rounded-2xl border bg-white px-5 pt-3 pb-4"
      >
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-gray-80">Admin 권한 부여</DialogTitle>
          <button type="button" onClick={() => onOpenChange(false)} className="cursor-pointer" aria-label="닫기">
            <Cancel className="size-5 text-gray-50" />
          </button>
        </div>

        <div className="border-neutral-3 flex w-[360px] flex-col gap-4 border-t pt-4">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1">
              <span className="text-body-small text-gray-80">부여할 멤버</span>
              <span className="bg-red-50 size-1.25 rounded-full" />
            </div>
            <Select value={memberId} onValueChange={setMemberId}>
              <SelectTrigger className="h-[46px]">
                <SelectValue placeholder="멤버 선택" />
              </SelectTrigger>
              <SelectContent>
                {members.map((member) => (
                  <SelectItem key={member.id} value={member.id}>
                    {member.name} ({member.department})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-body-small text-gray-80">부여 사유를 입력해주세요.</span>
              <span className="bg-red-50 size-1.25 rounded-full" />
            </div>
            <Input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="사유를 입력해주세요."
              className="h-[46px]"
            />
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
            onClick={() => onSubmit({ memberId, reason: reason.trim(), source: 'grant' })}
          >
            권한 부여
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AdminGrantModal;
