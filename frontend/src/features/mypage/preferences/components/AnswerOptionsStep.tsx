'use client';

import { Chip, ChipGroup } from '@/shared/components/ui/chips';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';

import { ANSWER_OPTIONS } from '../constants/preferencesConfig';
import type { AnswerOption } from '../types/preferencesModel';
import StepHeader from './StepHeader';

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
        <ChipGroup
          mode="multi"
          value={selectedOptions as string[]}
          onChange={(val) => {
            const arr = val as string[];
            const added = arr.find((v) => !selectedOptions.includes(v as AnswerOption));
            const removed = selectedOptions.find((v) => !arr.includes(v));
            const changed = added ?? removed;
            if (changed) onToggleOption(changed as AnswerOption);
          }}
          className="max-w-145 gap-x-2.5 gap-y-3"
        >
          {ANSWER_OPTIONS.map((opt) => (
            <Tooltip key={opt.value}>
              <TooltipTrigger asChild>
                <Chip
                  value={opt.value}
                  variant="capsule"
                  leadingIcon={<opt.icon />}
                >
                  {opt.label}
                </Chip>
              </TooltipTrigger>
              <TooltipContent size="sm" side="top">
                {opt.tooltip}
              </TooltipContent>
            </Tooltip>
          ))}
        </ChipGroup>
      </TooltipProvider>
    </div>
  );
}
