'use client';

import type { ComponentProps } from 'react';

import { Button } from '@/shared/components/ui/button';

import type { OnboardingStepInfo } from '../../types/llmWikiOnboarding';
import DocKindSelectField from './DocKindSelectField';
import OnboardingFieldLabel from './OnboardingFieldLabel';
import OnboardingStepper from './OnboardingStepper';
import PurposeSelectField from './PurposeSelectField';
import ToneStyleField from './ToneStyleField';

interface WikiOnboardingPurposeStepProps {
  steps: readonly OnboardingStepInfo[];
  heading: string;
  basicInfoTitle: string;
  nameLabel: string;
  nameValue: string;
  onNameChange?: (next: string) => void;
  namePlaceholder: string;
  nameMaxLength: number;
  purpose: ComponentProps<typeof PurposeSelectField>;
  formatTitle: string;
  docKind: ComponentProps<typeof DocKindSelectField>;
  tone: ComponentProps<typeof ToneStyleField>;
  nextLabel: string;
  onNext?: () => void;
}

// 온보딩 1단계 화면 조립. 검증 실패·버튼 비활성 상태는 시안에 없어 항상 활성으로 그린다
export default function WikiOnboardingPurposeStep({
  steps,
  heading,
  basicInfoTitle,
  nameLabel,
  nameValue,
  onNameChange,
  namePlaceholder,
  nameMaxLength,
  purpose,
  formatTitle,
  docKind,
  tone,
  nextLabel,
  onNext,
}: WikiOnboardingPurposeStepProps) {
  return (
    <div className="flex w-full flex-col">
      <div className="flex flex-col gap-8 px-16 pt-5 pb-9">
        <OnboardingStepper steps={steps} currentStep={1} />
        <h1 className="text-display-xlarge text-text-normal-strong">{heading}</h1>

        <div className="flex flex-col gap-5">
          <section className="bg-fill-normal-assistive border-line-normal-neutral flex flex-col gap-8 rounded-2xl border p-8">
            <h2 className="text-heading-large text-text-normal-strong">{basicInfoTitle}</h2>

            <div className="flex items-center">
              <OnboardingFieldLabel label={nameLabel} required className="w-[157px] shrink-0" />
              <div className="border-line-normal-neutral bg-fill-normal-normal flex h-11.5 min-w-0 flex-1 items-center gap-3 rounded-xl border px-4">
                <input
                  type="text"
                  value={nameValue}
                  maxLength={nameMaxLength}
                  placeholder={namePlaceholder}
                  aria-label={nameLabel}
                  onChange={(event) => onNameChange?.(event.target.value)}
                  className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive min-w-0 flex-1 bg-transparent outline-none"
                />
                <span className="text-body-small text-text-normal-assistive shrink-0">
                  {nameValue.length}/{nameMaxLength}
                </span>
              </div>
            </div>

            <PurposeSelectField {...purpose} />
          </section>

          <section className="bg-fill-normal-assistive border-line-normal-neutral flex flex-col gap-8 rounded-2xl border p-8">
            <h2 className="text-heading-large text-text-normal-strong">{formatTitle}</h2>
            <DocKindSelectField {...docKind} />
            <ToneStyleField {...tone} />
          </section>
        </div>
      </div>

      <div className="border-line-normal-neutral flex justify-end border-t px-16 py-2">
        <Button variant="box-solid-primary" size="md" onClick={onNext}>
          {nextLabel}
        </Button>
      </div>
    </div>
  );
}
