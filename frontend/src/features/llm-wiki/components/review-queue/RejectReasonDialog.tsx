'use client';

import { useState } from 'react';

import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/shared/components/ui/dialog';

export interface RejectReasonDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 제출 중이면 버튼을 잠근다 — 같은 반려가 두 번 나가지 않게 */
  submitting?: boolean;
  onSubmit: (reason: string) => void;
}

/** 닫히면 통째로 언마운트돼 이전 사유가 남지 않는다 */
function RejectReasonForm({
  submitting,
  onCancel,
  onSubmit,
}: {
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const trimmed = reason.trim();

  return (
    <>
      <div className="flex flex-col gap-3">
        <DialogTitle className="text-heading-medium text-text-normal-normal">전체 반려</DialogTitle>
        <DialogDescription>반려 사유는 작성자에게 그대로 전달됩니다.</DialogDescription>
      </div>

      <textarea
        autoFocus
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        placeholder="반려 사유를 입력해 주세요."
        rows={4}
        aria-label="반려 사유"
        className="border-line-normal-neutral text-body-small text-text-normal-normal placeholder:text-text-normal-assistive focus:border-line-primary-normal bg-fill-normal-normal w-full resize-none rounded-xl border px-4 py-3 outline-none"
      />

      <div className="flex justify-end gap-2.5">
        <Button variant="capsule-outline-mono" size="lg" onClick={onCancel}>
          취소
        </Button>
        <Button
          variant="capsule-solid-primary"
          size="lg"
          disabled={trimmed.length === 0 || submitting}
          onClick={() => onSubmit(trimmed)}
        >
          전체 반려
        </Button>
      </div>
    </>
  );
}

/**
 * 변경안 통째 반려의 사유 입력. 서버가 빈 사유를 400으로 막아 진입점에서 먼저 잠근다.
 * 전용 시안이 없어 ConfirmDialog의 여백·보더·버튼 배치를 그대로 따른다.
 */
export default function RejectReasonDialog({
  open,
  onOpenChange,
  submitting = false,
  onSubmit,
}: RejectReasonDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent hideClose className="border-line-normal-neutral flex max-w-122.75 flex-col gap-3 border p-5">
        <RejectReasonForm submitting={submitting} onCancel={() => onOpenChange(false)} onSubmit={onSubmit} />
      </DialogContent>
    </Dialog>
  );
}
