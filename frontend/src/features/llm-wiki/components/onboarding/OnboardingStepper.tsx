import { cn } from '@/shared/utils/cn';

import type { OnboardingStepInfo } from '../../types/llmWikiOnboarding';

interface OnboardingStepperProps {
  steps: readonly OnboardingStepInfo[];
  /** 현재 단계 번호 — 시안에 완료·비활성 등 다른 시각 상태는 없다 */
  currentStep: number;
}

// 온보딩 상단 단계 세그먼트. 진행 표시 전용이라 버튼이 아니다(시안에 클릭 동작 없음)
export default function OnboardingStepper({ steps, currentStep }: OnboardingStepperProps) {
  return (
    <ol className="bg-fill-normal-strong flex w-full items-stretch rounded-xl p-1" aria-label="온보딩 단계">
      {steps.map((step) => {
        const active = step.number === currentStep;

        return (
          <li
            key={step.number}
            aria-current={active ? 'step' : undefined}
            className={cn(
              'flex min-w-0 flex-1 items-center gap-3 rounded-lg px-3 py-1.5',
              active && 'bg-fill-normal-normal shadow-card',
            )}
          >
            <span
              className={cn(
                'text-body-small flex size-6.5 shrink-0 items-center justify-center rounded-full',
                active
                  ? 'bg-fill-normal-strong text-text-normal-strong'
                  : 'bg-fill-normal-normal text-text-normal-alternative',
              )}
            >
              {step.number}
            </span>
            <span
              className={cn(
                'text-body-small truncate',
                active ? 'text-text-normal-strong' : 'text-text-normal-alternative',
              )}
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
