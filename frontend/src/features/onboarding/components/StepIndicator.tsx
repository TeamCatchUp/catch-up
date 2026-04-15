'use client';

import { cn } from '@/shared/utils/cn';

interface StepIndicatorProps {
  totalSteps: number;
  currentStep: number;
}

export function StepIndicator({ totalSteps, currentStep }: StepIndicatorProps) {
  return (
    <div className="flex items-start gap-5">
      {Array.from({ length: totalSteps }, (_, i) => {
        const stepNum = i + 1;
        const isActive = stepNum <= currentStep;
        return (
          <div
            key={stepNum}
            className={cn(
              'border-edge-primary-assistive flex size-9.5 items-center justify-center overflow-hidden rounded-full border-[5px]',
              isActive ? 'bg-fill-primary' : 'bg-fill-primary-interaction-inactive',
            )}
          >
            <span className="text-heading-medium text-white">{stepNum}</span>
          </div>
        );
      })}
    </div>
  );
}
