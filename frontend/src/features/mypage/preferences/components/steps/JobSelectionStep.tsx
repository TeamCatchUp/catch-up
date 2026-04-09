'use client';

import { useState } from 'react';

import IconAddCircleFilled from '@/public/icons/icon/add_circle_filled.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconErrorFilled from '@/public/icons/icon/error_filled.svg';
import { Chip } from '@/shared/components/ui/chips';
import { cn } from '@/shared/utils/cn';

import {
  JOB_ROLE_OPTIONS,
  MAX_JOB_DESCRIPTION_LENGTH,
  MAX_JOB_TEXT_LENGTH,
} from '../../constants/preferencesConfig';
import type { JobRole } from '../../types/preferencesModel';
import StepHeader from '../StepHeader';

interface JobSelectionStepProps {
  selectedJob: JobRole | null;
  customJobText: string;
  jobDescription: string;
  onJobChange: (job: JobRole | null) => void;
  onCustomJobTextChange: (text: string) => void;
  onJobDescriptionChange: (text: string) => void;
}

export default function JobSelectionStep({
  selectedJob,
  customJobText,
  jobDescription,
  onJobChange,
  onCustomJobTextChange,
  onJobDescriptionChange,
}: JobSelectionStepProps) {
  const [jobFieldFocused, setJobFieldFocused] = useState(false);
  const [descFieldFocused, setDescFieldFocused] = useState(false);
  const isCustom = selectedJob === 'custom';
  const hasJob = selectedJob !== null;
  const isJobTextAtLimit = customJobText.length >= MAX_JOB_TEXT_LENGTH;
  const isDescAtLimit = jobDescription.length >= MAX_JOB_DESCRIPTION_LENGTH;
  const isDescDisabled = isCustom && customJobText.trim().length === 0;

  return (
    <div className="border-edge-neutral flex flex-col gap-5 border-b py-5">
      <StepHeader
        stepNumber={1}
        title="직무 선택"
        description="어떤 일을 하고 계신가요? 그에 맞게 답해드릴게요."
      />

      {/* 칩 그리드 */}
      <div className="flex flex-wrap gap-2.5">
        {JOB_ROLE_OPTIONS.map((opt) => {
          const isSelected = selectedJob === opt.value;
          return (
            <Chip
              key={opt.value}
              variant="square"
              selected={isSelected}
              trailingIcon={isSelected ? <IconCheckCircleFilled /> : undefined}
              onClick={() => onJobChange(isSelected ? null : opt.value)}
            >
              {opt.label}
            </Chip>
          );
        })}
      </div>

      {/* 직무 선택 후 표시되는 카드 */}
      {hasJob && (
        <div className="border-edge-assistive bg-fill-strong flex flex-col gap-5 overflow-clip rounded-xl border p-5">
          {/* "직접 입력" 선택 시: 직무 입력 필드 */}
          {isCustom && (
            <>
              <div className="flex flex-col gap-2.5">
                <div className="flex items-center gap-2.5">
                  <IconAddCircleFilled className="text-icon-primary size-6 shrink-0" />
                  <span className="text-heading-small text-content-normal">직무 직접 입력하기</span>
                </div>
                <div
                  className={cn(
                    'bg-fill-normal flex h-11.5 items-center rounded-lg p-3',
                    isJobTextAtLimit
                      ? 'border border-status-destructive'
                      : jobFieldFocused
                        ? 'border-[1.2px] border-edge-primary'
                        : 'border border-edge-neutral',
                  )}
                >
                  <input
                    className="text-body-small text-content-normal placeholder:text-content-assistive flex-1 bg-transparent outline-none"
                    placeholder="직무를 입력해주세요."
                    maxLength={MAX_JOB_TEXT_LENGTH}
                    value={customJobText}
                    onChange={(e) => onCustomJobTextChange(e.target.value)}
                    onFocus={() => setJobFieldFocused(true)}
                    onBlur={() => setJobFieldFocused(false)}
                  />
                  <span className="text-body-small text-content-alternative shrink-0">
                    {customJobText.length}/{MAX_JOB_TEXT_LENGTH}
                  </span>
                </div>
                {isJobTextAtLimit && (
                  <div className="flex items-center gap-0.5">
                    <IconErrorFilled className="text-status-destructive size-4 shrink-0" />
                    <span className="text-label-xsmall text-status-destructive">
                      {MAX_JOB_TEXT_LENGTH}자 내외로 입력해주세요.
                    </span>
                  </div>
                )}
              </div>
              {/* 구분선 */}
              <div className="border-edge-neutral border-t" />
            </>
          )}

          {/* 업무 설명 필드 */}
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-2.5">
              <IconAddCircleFilled className="text-icon-primary size-6 shrink-0" />
              <span className="text-heading-small text-content-normal">주로 어떤 업무를 맡고 있나요?</span>
            </div>
            <div className="flex flex-col gap-1.5">
              <div
                className={cn(
                  'flex h-11.5 items-center rounded-lg p-3',
                  isDescDisabled
                    ? 'bg-fill-interaction-disable border border-edge-neutral'
                    : isDescAtLimit
                      ? 'bg-fill-normal border border-status-destructive'
                      : descFieldFocused
                        ? 'bg-fill-normal border-[1.2px] border-edge-primary'
                        : 'bg-fill-normal border border-edge-neutral',
                )}
              >
                <input
                  className={cn(
                    'text-body-small flex-1 bg-transparent outline-none',
                    isDescDisabled
                      ? 'text-content-normal cursor-not-allowed'
                      : 'text-content-normal placeholder:text-content-assistive',
                  )}
                  placeholder={isDescDisabled ? '직무를 먼저 입력해주세요.' : '주요 업무를 간단히 입력해주세요.'}
                  maxLength={MAX_JOB_DESCRIPTION_LENGTH}
                  value={jobDescription}
                  onChange={(e) => onJobDescriptionChange(e.target.value)}
                  onFocus={() => setDescFieldFocused(true)}
                  onBlur={() => setDescFieldFocused(false)}
                  disabled={isDescDisabled}
                />
                {!isDescDisabled && (
                  <span className="text-body-small text-content-alternative shrink-0">
                    {jobDescription.length}/{MAX_JOB_DESCRIPTION_LENGTH}
                  </span>
                )}
              </div>
              {isDescAtLimit && (
                <div className="flex items-center gap-0.5">
                  <IconErrorFilled className="text-status-destructive size-4 shrink-0" />
                  <span className="text-label-xsmall text-status-destructive">
                    {MAX_JOB_DESCRIPTION_LENGTH}자 내외로 입력해주세요.
                  </span>
                </div>
              )}
              <div className="text-label-xsmall text-content-alternative flex flex-col">
                <span>{` 예) "iOS 앱 성능 최적화와 배포 파이프라인을 주로 담당해요"`}</span>
                <span>{` 예) "B2B 영업 제안서 작성과 고객사 기술 미팅 대응이 많아요"`}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
