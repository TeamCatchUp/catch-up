'use client';

import { Chip } from '@/shared/components/ui/chips';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';

import { ANSWER_OPTIONS } from '../../constants/preferencesConfig';
import type { AnswerOption } from '../../types/preferencesModel';
import StepHeader from '../StepHeader';

interface AnswerOptionsStepProps {
  selectedOptions: AnswerOption[];
  onToggleOption: (option: AnswerOption) => void;
}

export default function AnswerOptionsStep({ selectedOptions, onToggleOption }: AnswerOptionsStepProps) {
  return (
    <div className="border-edge-neutral flex flex-col gap-5 border-b py-5">
      <StepHeader
        stepNumber={2}
        title="맞춤형 답변 옵션 선택"
        description="선택한 항목이 답변마다 자동으로 포함돼요."
      />

      <TooltipProvider>
        <div className="flex max-w-145 flex-wrap gap-x-2.5 gap-y-3">
          {ANSWER_OPTIONS.map((opt) => {
            const isSelected = selectedOptions.includes(opt.value);
            return (
              <Tooltip key={opt.value}>
                <TooltipTrigger asChild>
                  <Chip
                    variant="capsule"
                    selected={isSelected}
                    leadingIcon={<opt.icon />}
                    onClick={() => onToggleOption(opt.value)}
                  >
                    {opt.label}
                  </Chip>
                </TooltipTrigger>
                <TooltipContent size="sm" side="bottom">
                  {opt.tooltip}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </TooltipProvider>
    </div>
  );
}
