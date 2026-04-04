'use client';

import { useMemo, useState } from 'react';

import Cancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';

import { PERMISSION_ROLE_CHANGE_REASONS, ROLE_LABEL } from '../../constants/permissionsConfig';
import type { PermissionMember, PermissionRole } from '../../types/adminPermissionModel';

interface RoleChangeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  member: PermissionMember | null;
  isSubmitting: boolean;
  errorMessage?: string;
  onSubmit: (userId: number, reason: string) => void;
}

const NEW_ROLE_OPTIONS: { value: PermissionRole; label: string }[] = [{ value: 'user', label: 'Member' }];

/** 권한 변경 모달 (Admin → Member 회수) */
const RoleChangeModal = ({
  open,
  onOpenChange,
  member,
  isSubmitting,
  errorMessage,
  onSubmit,
}: RoleChangeModalProps) => {
  const [newRole, setNewRole] = useState<PermissionRole | ''>('');
  const [selectedReason, setSelectedReason] = useState<string>('');
  const [customReason, setCustomReason] = useState('');

  const finalReason = useMemo(() => {
    if (selectedReason !== '직접 입력') return selectedReason;
    return customReason.trim();
  }, [customReason, selectedReason]);

  const isSubmitDisabled = !member || !newRole || !finalReason || isSubmitting;

  const currentRoleLabel = member ? ROLE_LABEL[member.role] : '';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="border-edge-neutral shadow-modal bg-fill-normal max-w-140 gap-4 rounded-3xl border px-0 py-5"
      >
        {/* Header */}
        <div className="flex h-9 items-center justify-between px-6">
          <DialogTitle className="text-heading-large text-content-normal">권한 변경하기</DialogTitle>
          <button type="button" onClick={() => onOpenChange(false)} className="cursor-pointer" aria-label="닫기">
            <Cancel className="text-content-alternative size-5" />
          </button>
        </div>

        {/* Body */}
        <div className="border-edge-assistive flex flex-col gap-6 overflow-y-auto border-t px-6 pt-6">
          {/* 권한 정보 */}
          <div className="flex flex-col gap-2">
            <span className="text-body-medium text-content-normal">권한 정보</span>
            <div className="border-edge-normal border-t">
              <div className="border-edge-normal flex h-12 items-center border-b">
                <div className="bg-fill-primary-assistive flex h-full w-36.25 items-center px-4">
                  <span className="text-body-small text-content-neutral">권한 변경 대상</span>
                </div>
                <div className="flex flex-1 items-center px-4">
                  <span className="text-body-small text-content-neutral truncate">
                    {member ? `${member.name}(${member.department})` : ''}
                  </span>
                </div>
              </div>
              <div className="border-edge-normal flex h-12 items-center border-b">
                <div className="bg-fill-primary-assistive flex h-full w-36.25 items-center px-4">
                  <span className="text-body-small text-content-neutral">기존 권한</span>
                </div>
                <div className="flex flex-1 items-center px-4">
                  <span className="text-body-small text-content-neutral">{currentRoleLabel}</span>
                </div>
              </div>
            </div>
          </div>

          {/* 새로운 권한 */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-body-medium text-content-normal">새로운 권한</span>
              <span className="bg-status-destructive size-1.25 rounded-full" />
            </div>
            <Select value={newRole} onValueChange={(v) => setNewRole(v as PermissionRole)}>
              <SelectTrigger className="h-11.5">
                <SelectValue placeholder="변경할 권한을 선택해주세요." />
              </SelectTrigger>
              <SelectContent>
                {NEW_ROLE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 사유 선택 */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1">
              <span className="text-body-medium text-content-strong">권한 조정 사유를 선택해주세요.</span>
              <span className="bg-status-destructive size-1.25 rounded-full" />
            </div>

            <div className="border-edge-assistive flex flex-col gap-4 rounded-xl border px-4 py-4">
              {PERMISSION_ROLE_CHANGE_REASONS.map((reason) => {
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

            <p className="text-label-xsmall text-content-assistive">
              워크스페이스 설정, 멤버 권한 제어 등 관리자 전용 기능에 더 이상 접근할 수 없습니다.
            </p>
          </div>

          {errorMessage && <p className="text-label-xsmall text-status-destructive">{errorMessage}</p>}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6">
          <Button variant="capsule-outline-mono" size="md" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            닫기
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="md"
            disabled={isSubmitDisabled}
            onClick={() => member && onSubmit(member.id, finalReason)}
          >
            권한 변경하기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default RoleChangeModal;
