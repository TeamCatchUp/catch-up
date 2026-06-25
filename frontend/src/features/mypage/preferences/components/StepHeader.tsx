'use client';

interface StepHeaderProps {
  stepNumber: number;
  title: string;
  description: string;
}

export default function StepHeader({ stepNumber, title, description }: StepHeaderProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <div className="border-line-normal-assistive bg-fill-normal-strong flex size-6 shrink-0 items-center justify-center rounded-full border">
          <span className="text-body-small text-text-normal-alternative">{stepNumber}</span>
        </div>
        <span className="text-heading-medium text-text-normal-normal">{title}</span>
      </div>
      <span className="text-label-small text-text-normal-alternative">{description}</span>
    </div>
  );
}
