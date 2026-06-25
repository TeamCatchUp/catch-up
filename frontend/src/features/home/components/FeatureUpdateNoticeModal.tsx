'use client';

import { useState } from 'react';
import Image from 'next/image';

import Cancel from '@/public/icons/icon/cancel.svg';
import LightbulbFilled from '@/public/icons/icon/lightbulb_filled.svg';
import Megaphone from '@/public/icons/icon/megaphone.svg';
import { Button } from '@/shared/components/ui/button';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/shared/components/ui/dialog';

import { FEATURE_UPDATE_NOTICE } from '../constants/featureUpdateNotice';

interface FeatureUpdateNoticeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  onDismiss?: () => void;
}

// 신규 기능 업데이트 공지 팝업.
export default function FeatureUpdateNoticeModal({
  open,
  onOpenChange,
  onConfirm,
  onDismiss,
}: FeatureUpdateNoticeModalProps) {
  const [dontShowAgain, setDontShowAgain] = useState(false);
  const notice = FEATURE_UPDATE_NOTICE;

  const handleClose = () => {
    if (dontShowAgain) onDismiss?.();
    onOpenChange(false);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next && dontShowAgain) onDismiss?.();
    onOpenChange(next);
  };

  const handleCTA = () => {
    if (dontShowAgain) onDismiss?.();
    onOpenChange(false);
    onConfirm();
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        hideClose
        className="border-line-normal-strong flex w-175 max-w-none flex-col gap-2 rounded-3xl border p-8"
      >
        {/* 컬럼 1: 헤더 + 미디어 + 본문 + 불릿 + 팁 */}
        <div className="flex flex-col gap-6">
          {/* 헤더 */}
          <div className="flex items-start gap-6">
            <div className="flex flex-1 flex-col gap-3">
              <span className="bg-fill-primary-normal-neutral rounded-md2 inline-flex w-fit items-center gap-1 px-1.5 py-0.5">
                <Megaphone className="text-icon-primary-normal size-4.5" aria-hidden="true" />
                <span className="text-body-xsmall text-text-primary-normal">{notice.tagLabel}</span>
              </span>
              <DialogTitle className="text-heading-xlarge text-text-normal-strong">{notice.title}</DialogTitle>
              <p className="text-body-medium text-text-normal-normal">{notice.subtitle}</p>
            </div>
            <Button
              variant="icon-outline-gray"
              size="lg"
              aria-label="닫기"
              onClick={handleClose}
              className="size-10 shrink-0 p-1.5"
            >
              <Cancel className="size-7" aria-hidden="true" />
            </Button>
          </div>

          {/* 미디어 */}
          <div className="relative h-50 w-full overflow-hidden rounded-xl">
            <Image src={notice.imageSrc} alt={notice.imageAlt} fill className="object-cover dark:hidden" priority />
            <Image src={notice.imageDarkSrc} alt={notice.imageAlt} fill className="hidden object-cover dark:block" />
          </div>

          {/* 본문 */}
          <DialogDescription asChild>
            <p className="text-body-small text-text-normal-normal">
              이제 Claude에서도 <span className="text-text-primary-normal">Catch Up</span>의 검색 경험을 사용할 수
              있습니다.
              <br />
              회사에 흩어진 Slack, Jira, Confluence, GitHub, ChannelTalk 데이터를 기반으로 필요한 정보를 찾아보세요.
            </p>
          </DialogDescription>

          {/* 팁 박스 */}
          <div className="bg-fill-normal-normal border-line-normal-normal flex items-center gap-4 rounded-xl border px-4 py-3">
            <div className="bg-fill-primary-normal-neutral flex size-9.5 shrink-0 items-center justify-center rounded-lg">
              <LightbulbFilled className="text-icon-primary-assistive size-5.5" aria-hidden="true" />
            </div>
            <p className="text-body-small text-text-normal-normal">
              Catch Up MCP 하나만 연결하면 됩니다. Slack, Jira, Confluence, GitHub, ChannelTalk를 각각 연결할 필요 없이
              여러 업무 도구를 한 번에 탐색할 수 있습니다.
            </p>
          </div>
        </div>

        {/* 푸터: 체크박스 + CTA */}
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
            <span className="text-body-small text-text-normal-alternative">다시 보지 않기</span>
          </label>
          <Button
            variant="box-solid-primary"
            size="lg"
            onClick={handleCTA}
            className="border-line-normal-neutral text-body-medium h-11.5 w-full border"
          >
            {notice.ctaLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
