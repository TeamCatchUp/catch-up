'use client';

import { useState } from 'react';

import Cancel from '@/public/icons/icon/cancel.svg';
import Megaphone from '@/public/icons/icon/megaphone.svg';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/shared/components/ui/dialog';
import type { ServiceNoticeContent } from '@/shared/constants/serviceNotices';

interface ServiceNoticeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  notice: ServiceNoticeContent;
  /** "다시 보지 않기" 체크 후 닫을 때 호출 */
  onDismiss?: () => void;
}

/** 서비스 장애/정상화 공지 팝업 */
export default function ServiceNoticeModal({ open, onOpenChange, notice, onDismiss }: ServiceNoticeModalProps) {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  const handleClose = () => {
    if (dontShowAgain) onDismiss?.();
    onOpenChange(false);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next && dontShowAgain) onDismiss?.();
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent hideClose className="border-edge-normal w-120 max-w-none gap-5 border p-6">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="bg-fill-primary-normal-neutral rounded-md2 flex items-center gap-1 px-1.5 py-0.5">
              <Megaphone className="text-content-primary size-4.5" aria-hidden="true" />
              <span className="text-body-xsmall text-content-primary">공지</span>
            </span>
            <button
              type="button"
              aria-label="닫기"
              onClick={handleClose}
              className="border-edge-neutral bg-fill-normal flex size-9 cursor-pointer items-center justify-center rounded-lg border p-1.5"
            >
              <Cancel className="text-icon-normal size-6" aria-hidden="true" />
            </button>
          </div>

          <DialogTitle>{notice.title}</DialogTitle>
          <DialogDescription className="sr-only">서비스 장애 또는 정상화에 대한 공지 내용입니다.</DialogDescription>

          <section className="bg-fill-primary-assistive text-body-small text-content-normal space-y-5.5 rounded-xl p-5">
            {notice.body}
          </section>
        </div>

        <div className="flex flex-col gap-2">
          <label className="flex w-fit cursor-pointer items-center gap-1">
            <span aria-hidden="true">
              <CheckboxIcon checked={dontShowAgain} className="size-5" />
            </span>
            <input
              type="checkbox"
              className="sr-only"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
            />
            <span className="text-body-small text-content-alternative">다시 보지 않기</span>
          </label>
          <button
            type="button"
            onClick={handleClose}
            className="border-edge-neutral bg-fill-normal text-body-medium text-content-neutral hover:bg-fill-interaction-hover flex h-11.5 w-full cursor-pointer items-center justify-center rounded-lg border px-4 py-1.5"
          >
            닫기
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
