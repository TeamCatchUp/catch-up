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
  /** 'danger' 시 확인 버튼이 빨간색 아웃라인으로 표시 */
  variant?: 'primary' | 'danger';
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
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent hideClose className="flex max-w-[491px] flex-col gap-3 border border-neutral-3 p-5">
        <div className="flex flex-col gap-3">
          <DialogTitle className="text-heading-medium text-gray-80">{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </div>
        <div className="flex justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="lg" onClick={() => onOpenChange(false)}>
            {cancelLabel}
          </Button>
          <Button
            variant={variant === 'danger' ? 'capsule-outline-mono' : 'capsule-solid-primary'}
            size="lg"
            className={cn(
              variant === 'danger' &&
                'border-red-40 text-red-50 hover:bg-red-5 active:border-red-50 active:bg-red-10',
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
