'use client';

import { useState } from 'react';

import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconError from '@/public/icons/icon/error.svg';
import { Chip, ChipGroup } from '@/shared/components/ui/chips';
import { cn } from '@/shared/utils/cn';

import { JOB_ROLE_OPTIONS, MAX_JOB_TEXT_LENGTH } from '../constants/preferencesConfig';
import type { JobRole } from '../types/preferencesModel';
import StepHeader from './StepHeader';

interface JobSelectionStepProps {
  selectedJob: JobRole | null;
  customJobText: string;
  onJobChange: (job: JobRole | null) => void;
  onCustomJobTextChange: (text: string) => void;
}

export default function JobSelectionStep({
  selectedJob,
  customJobText,
  onJobChange,
  onCustomJobTextChange,
}: JobSelectionStepProps) {
  const [isFocused, setIsFocused] = useState(false);
  const isOverLimit = customJobText.length > MAX_JOB_TEXT_LENGTH;

  return (
    <div className="border-edge-neutral flex flex-col gap-5 border-b py-5">
      <StepHeader
        stepNumber={1}
        title="직무 선택"
        description="어떤 일을 하고 계신가요? 그에 맞게 답해드릴게요."
      />

      <ChipGroup
        mode="single"
        value={selectedJob ?? ''}
        onChange={(val) => onJobChange((val as JobRole) || null)}
      >
        {JOB_ROLE_OPTIONS.map((opt) => {
          const isSelected = selectedJob === opt.value;
          return (
            <Chip
              key={opt.value}
              value={opt.value}
              variant="square"
              leadingIcon={isSelected ? <IconCheckCircleFilled /> : undefined}
              trailingIcon={isSelected ? <IconCheckCircleFilled /> : undefined}
            >
              {opt.label}
            </Chip>
          );
        })}
      </ChipGroup>

      {selectedJob === 'custom' && (
        <div className="flex flex-col gap-1.5">
          <div
            className={cn(
              'bg-fill-normal flex items-center rounded-lg p-3',
              isOverLimit ? 'border border-status-destructive' : isFocused ? 'border-[1.2px] border-primary-normal' : 'border border-edge-neutral',
            )}
          >
            <input
              className="text-body-small text-content-normal placeholder:text-content-assistive flex-1 bg-transparent outline-none"
              placeholder="직무를 입력해주세요."
              maxLength={MAX_JOB_TEXT_LENGTH}
              value={customJobText}
              onChange={(e) => onCustomJobTextChange(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
            />
            <span className="text-body-small text-content-alternative shrink-0">
              {customJobText.length}/{MAX_JOB_TEXT_LENGTH}
            </span>
          </div>
          {isOverLimit && (
            <div className="flex items-center gap-0.5">
              <IconError className="text-status-destructive h-4 w-4" />
              <span className="text-label-xsmall text-status-destructive">
                {MAX_JOB_TEXT_LENGTH}자 이내로 입력해주세요.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
