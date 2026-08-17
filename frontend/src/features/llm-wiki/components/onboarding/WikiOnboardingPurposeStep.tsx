'use client';

import type { ComponentProps } from 'react';

import { Input } from '@/shared/components/ui/input';

import type { OnboardingStepInfo } from '../../types/llmWikiOnboarding';
import DocKindSelectField from './DocKindSelectField';
import OnboardingActionBar from './OnboardingActionBar';
import OnboardingFieldLabel from './OnboardingFieldLabel';
import OnboardingStepper from './OnboardingStepper';
import OnboardingTopBar from './OnboardingTopBar';
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
  docSettingTitle: string;
  docKind: ComponentProps<typeof DocKindSelectField>;
  tone: ComponentProps<typeof ToneStyleField>;
  nextLabel: string;
  onNext?: () => void;
  /** 상단 바 뒤로가기 — 하단 "이전"(단계 후퇴)과 달리 온보딩을 벗어난다 */
  onExit?: () => void;
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
  docSettingTitle,
  docKind,
  tone,
  nextLabel,
  onNext,
  onExit,
}: WikiOnboardingPurposeStepProps) {
  return (
    <div className="bg-fill-normal-assistive flex w-full flex-col">
      <OnboardingTopBar onBack={onExit} />
      <div className="flex flex-col gap-8 px-16 pt-5 pb-9">
        <OnboardingStepper steps={steps} currentStep={1} />
        <h1 className="text-heading-xlarge text-text-normal-normal">{heading}</h1>

        <div className="flex flex-col gap-5">
          <section className="bg-fill-normal-normal border-line-normal-neutral flex flex-col gap-8 rounded-2xl border p-8">
            <h2 className="text-heading-large text-text-normal-normal">{basicInfoTitle}</h2>

            <div className="flex items-center">
              <OnboardingFieldLabel label={nameLabel} required className="w-[157px] shrink-0" />
              {/* 카운터는 Textfield 컴포넌트 몫이라 공용 Input 위에 겹쳐 놓는다 */}
              <div className="relative min-w-0 flex-1">
                <Input
                  type="text"
                  value={nameValue}
                  maxLength={nameMaxLength}
                  placeholder={namePlaceholder}
                  aria-label={nameLabel}
                  onChange={(event) => onNameChange?.(event.target.value)}
                  className="pr-16"
                />
                <span className="text-body-small text-text-normal-alternative absolute top-1/2 right-3 -translate-y-1/2">
                  {nameValue.length}/{nameMaxLength}
                </span>
              </div>
            </div>

            <PurposeSelectField {...purpose} />
          </section>

          <section className="bg-fill-normal-normal border-line-normal-neutral flex flex-col gap-8 rounded-2xl border p-8">
            <h2 className="text-heading-large text-text-normal-normal">{docSettingTitle}</h2>
            <DocKindSelectField {...docKind} />
            <ToneStyleField {...tone} />
          </section>
        </div>
      </div>

      <OnboardingActionBar nextLabel={nextLabel} onNext={onNext} />
    </div>
  );
}
