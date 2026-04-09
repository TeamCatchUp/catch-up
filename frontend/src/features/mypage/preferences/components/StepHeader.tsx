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
        <div className="border-edge-assistive bg-fill-strong flex size-6 shrink-0 items-center justify-center rounded-full border">
          <span className="text-body-small text-content-alternative">{stepNumber}</span>
        </div>
        <span className="text-heading-medium text-content-normal">{title}</span>
      </div>
      <span className="text-label-small text-content-alternative">{description}</span>
    </div>
  );
}
