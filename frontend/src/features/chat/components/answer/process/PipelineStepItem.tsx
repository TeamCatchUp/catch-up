import type { ComponentType, SVGProps } from 'react';

import type { InlineStep, InlineStepIcon } from '@/features/chat/utils/process/buildInlineSteps';
import Assignment from '@/public/icons/icon/assignment.svg';
import CheckCircle from '@/public/icons/icon/check_circle.svg';
import EditPencil from '@/public/icons/icon/edit_pencil.svg';
import SearchFile from '@/public/icons/icon/search_file.svg';

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

const ICON_BY_KEY: Record<InlineStepIcon, IconComponent> = {
  request: SearchFile,
  rewrite: EditPencil,
  plan: CheckCircle,
  search: Assignment,
  done: CheckCircle,
};

interface PipelineStepItemProps {
  step: InlineStep;
  isLast: boolean;
}

export default function PipelineStepItem({ step, isLast }: PipelineStepItemProps) {
  const Icon = ICON_BY_KEY[step.icon];

  return (
    <div className="flex w-full items-stretch gap-5">
      <div className="flex w-5.5 shrink-0 flex-col items-center gap-0.5">
        <Icon className="text-icon-neutral h-5.5 w-5.5 shrink-0" aria-hidden />
        {!isLast && <span aria-hidden className="bg-edge-neutral w-px flex-1" />}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2 pb-3">
        <p className="text-body-xsmall text-content-alternative flex h-5.5 items-center">{step.title}</p>
        {step.lines.map((line, idx) => (
          <p key={idx} className="text-body-xsmall text-content-alternative wrap-break-word">
            {line}
          </p>
        ))}
      </div>
    </div>
  );
}
