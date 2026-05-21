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

// 신규 기능 업데이트 공지 팝업 (Figma: 13650:54095).
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
        className="border-edge-strong flex w-175 max-w-none flex-col gap-2 rounded-3xl border p-8"
      >
        {/* 컬럼 1: 헤더 + 미디어 + 본문 + 불릿 + 팁 */}
        <div className="flex flex-col gap-6">
          {/* 헤더 */}
          <div className="flex items-start gap-6">
            <div className="flex flex-1 flex-col gap-3">
              <span className="bg-fill-primary-normal-neutral rounded-md2 inline-flex w-fit items-center gap-1 px-1.5 py-0.5">
                <Megaphone className="text-icon-primary size-4.5" aria-hidden="true" />
                <span className="text-body-xsmall text-content-primary">{notice.tagLabel}</span>
              </span>
              <DialogTitle className="text-heading-xlarge text-content-strong">{notice.title}</DialogTitle>
              <p className="text-body-medium text-content-normal">{notice.subtitle}</p>
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
            <Image src={notice.imageSrc} alt={notice.imageAlt} fill className="object-cover" priority />
          </div>

          {/* 본문 */}
          <DialogDescription asChild>
            <p className="text-body-small text-content-normal">
              캐치업의 검색은 원래 <span className="text-content-primary">&quot;질문에 대한 답&quot;</span> 을
              만들어주는 데 최적화돼 있었어요. 그런데 고객분들과 이야기하면서 발견한 게 있어요 — 항상 명확한 질문이 있는
              건 아니라는 점이에요. 때로는{' '}
              <span className="text-content-primary">&quot;그 채용 자동화 관련 문서들 어디 있더라&quot;</span>
              처럼 둘러보고 싶을 때가 있죠.
              <br />
              그래서 검색을 두 가지 모드로 나눴어요
            </p>
          </DialogDescription>

          {/* 불릿 */}
          <ul className="flex flex-col gap-2.5">
            <li className="text-body-small text-content-normal flex items-center gap-3">
              <span className="bg-fill-interaction-pressed-hover size-2 shrink-0 rounded-full" aria-hidden="true" />
              <span>답변 모드 (기존): 구체적인 질문에 정리된 답을 받고 싶을 때</span>
            </li>
            <li className="text-body-small text-content-normal flex items-center gap-3">
              <span className="bg-fill-interaction-pressed-hover size-2 shrink-0 rounded-full" aria-hidden="true" />
              <span>
                <span className="text-content-primary">탐색 모드 (신규):</span> 관련된 Jira 티켓, Confluence 페이지,
                Slack 스레드를 한 번에 훑어보고 싶을 때
              </span>
            </li>
          </ul>

          {/* 팁 박스 */}
          <div className="bg-fill-normal border-edge-normal flex items-center gap-4 rounded-xl border px-4 py-3">
            <div className="bg-fill-primary-normal-neutral flex size-9.5 shrink-0 items-center justify-center rounded-lg">
              <LightbulbFilled className="text-icon-primary-assistive size-5.5" aria-hidden="true" />
            </div>
            <p className="text-body-small text-content-normal">
              한 단어로 검색해도 되지만, &quot;신입 개발자 온보딩 첫 주&quot;처럼 구체적으로 입력하면 의미가 비슷한
              문서까지 더 정확히 찾아드려요.
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
            <span className="text-body-small text-content-alternative">다시 보지 않기</span>
          </label>
          <Button
            variant="box-solid-primary"
            size="lg"
            onClick={handleCTA}
            className="border-edge-neutral text-body-medium h-11.5 w-full border"
          >
            {notice.ctaLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
