'use client';

import { Button } from '@/shared/components/ui/button';

interface StepNavButtonsProps {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  isNextDisabled?: boolean;
  showBack?: boolean;
}

export function StepNavButtons({
  onBack,
  onNext,
  nextLabel = '다음으로 넘어가기',
  isNextDisabled = false,
  showBack = true,
}: StepNavButtonsProps) {
  return (
    <div className="flex w-full items-center gap-[15px]">
      {showBack && onBack && (
        <Button type="button" variant="box-outline-gray" size="lg" onClick={onBack} className="h-[46px] shrink-0">
          이전
        </Button>
      )}
      <Button
        type="button"
        variant="box-solid-primary"
        size="lg"
        onClick={onNext}
        disabled={isNextDisabled}
        className="h-[46px] flex-1"
      >
        {nextLabel}
      </Button>
    </div>
  );
}
