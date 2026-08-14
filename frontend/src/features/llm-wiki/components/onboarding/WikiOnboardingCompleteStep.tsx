import IconCheck from '@/public/icons/icon/check.svg';

import type { OnboardingStepInfo, OnboardingSummarySection } from '../../types/llmWikiOnboarding';
import OnboardingActionBar from './OnboardingActionBar';
import OnboardingStepper from './OnboardingStepper';
import OnboardingSummaryCard from './OnboardingSummaryCard';

interface WikiOnboardingCompleteStepProps {
  steps: readonly OnboardingStepInfo[];
  heading: string;
  summarySections: readonly OnboardingSummarySection[];
  nextStepsTitle: string;
  /** 명세의 완료 화면 3요소(시간 약속 2 + 검수 안내 1). 별도 철학 문단은 시안에 없다 */
  nextSteps: readonly string[];
  backLabel: string;
  onBack?: () => void;
  finishLabel: string;
  onFinish?: () => void;
}

// 온보딩 3단계 확인·완료 화면. 제출 진행·성공·실패 상태는 시안에 없어 만들지 않는다
export default function WikiOnboardingCompleteStep({
  steps,
  heading,
  summarySections,
  nextStepsTitle,
  nextSteps,
  backLabel,
  onBack,
  finishLabel,
  onFinish,
}: WikiOnboardingCompleteStepProps) {
  return (
    <div className="flex w-full flex-col">
      <div className="flex flex-col gap-8 px-16 pt-5 pb-9">
        <OnboardingStepper steps={steps} currentStep={3} />
        <h1 className="text-heading-xlarge text-text-normal-normal">{heading}</h1>

        <div className="flex flex-col gap-5">
          <OnboardingSummaryCard sections={summarySections} />

          <div className="bg-fill-primary-normal-assistive flex flex-col gap-5 rounded-2xl p-6">
            <h2 className="text-heading-small text-text-primary-normal">{nextStepsTitle}</h2>
            <ul aria-label={nextStepsTitle} className="flex flex-col gap-2.5">
              {nextSteps.map((step) => (
                <li key={step} className="flex items-start gap-2">
                  <IconCheck className="text-icon-primary-assistive mt-0.5 size-5.5 shrink-0" />
                  <span className="text-body-small text-text-primary-normal">{step}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <OnboardingActionBar backLabel={backLabel} onBack={onBack} nextLabel={finishLabel} onNext={onFinish} />
    </div>
  );
}
