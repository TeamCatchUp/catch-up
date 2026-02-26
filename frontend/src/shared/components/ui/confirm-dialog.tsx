'use client';

import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/shared/components/ui/dialog';
import { cn } from '@/shared/utils/cn';

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** 'danger' 시 빨간색 아웃라인, 'blue' 시 파란색 아웃라인 */
  variant?: 'primary' | 'danger' | 'blue';
  /** 취소 버튼 숨김 (알림형 모달) */
  hideCancel?: boolean;
  onConfirm: () => void;
}

function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = '확인',
  cancelLabel = '취소',
  variant = 'primary',
  hideCancel = false,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent hideClose className="border-neutral-3 flex max-w-[491px] flex-col gap-3 border p-5">
        <div className="flex flex-col gap-3">
          <DialogTitle className="text-heading-medium text-gray-80">{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </div>
        <div className="flex justify-end gap-2.5">
          {!hideCancel && (
            <Button variant="capsule-outline-mono" size="lg" onClick={() => onOpenChange(false)}>
              {cancelLabel}
            </Button>
          )}
          <Button
            variant={
              variant === 'danger'
                ? 'capsule-outline-mono'
                : variant === 'blue'
                  ? 'capsule-outline-blue'
                  : 'capsule-solid-primary'
            }
            size="lg"
            className={cn(
              variant === 'danger' && 'border-red-40 hover:bg-red-5 active:bg-red-10 text-red-50 active:border-red-50',
            )}
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export { ConfirmDialog };
export type { ConfirmDialogProps };
