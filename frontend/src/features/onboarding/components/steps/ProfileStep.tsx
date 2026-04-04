'use client';

import { useState } from 'react';

import ErrorIcon from '@/public/icons/icon/error.svg';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { DEPARTMENT_OPTIONS, JOB_LEVEL_OPTIONS } from '@/shared/constants/organization';

import type { ProfileFormData } from '../../types/onboardingModel';
import { StepIndicator } from '../StepIndicator';
import { StepNavButtons } from '../StepNavButtons';

interface ProfileStepProps {
  isAdmin: boolean;
  defaultValues: {
    name: string;
    job_level: string;
    department: string;
  };
  onSubmit: (data: ProfileFormData) => void;
  onBack?: () => void;
}

export function ProfileStep({ isAdmin, defaultValues, onSubmit, onBack }: ProfileStepProps) {
  const [name, setName] = useState(defaultValues.name);
  const [jobLevel, setJobLevel] = useState(defaultValues.job_level);
  const [department, setDepartment] = useState(defaultValues.department);

  const [errors, setErrors] = useState<Record<string, boolean>>({});

  const validate = () => {
    const newErrors: Record<string, boolean> = {};
    if (!name.trim()) newErrors.name = true;
    if (!jobLevel) newErrors.jobLevel = true;
    if (!isAdmin && !department) newErrors.department = true;
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (!validate()) return;
    onSubmit({
      name: name.trim(),
      job_level: jobLevel as ProfileFormData['job_level'],
      ...(isAdmin ? {} : { department }),
    });
  };

  const isComplete = name.trim() && jobLevel && (isAdmin || department);

  return (
    <div className="flex size-full flex-col justify-between">
      <div className="flex flex-col gap-12">
        {/* 헤더 영역: 스텝 인디케이터 + 타이틀 + 설명 */}
        <div className="flex flex-col gap-4">
          {isAdmin && <StepIndicator totalSteps={2} currentStep={1} />}
          <h1 className="text-display-large text-content-normal">
            잠시만 시간을 내어
            <br />
            간단한 정보를 알려주세요.
          </h1>
          <p className="text-body-large text-content-alternative">성함과 맡고 계신 역할만 알려주셔도 충분합니다.</p>
        </div>

        {/* 폼 영역 */}
        <div className="flex flex-col gap-6">
          {/* 이름 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-heading-medium text-content-normal flex items-center gap-1">
              <span className="size-1.25 rounded-full bg-red-50" />
              이름을 적어주세요.
            </label>
            <Input
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (errors.name) setErrors((p) => ({ ...p, name: false }));
              }}
              placeholder="이름"
              error={errors.name}
              className="h-11.5"
            />
          </div>

          {/* 직급 + 부서명 */}
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-1.5">
              <label className="text-heading-medium text-content-normal flex items-center gap-1">
                <span className="size-1.25 rounded-full bg-red-50" />
                직급을 알려주세요.
              </label>
              <Select
                value={jobLevel}
                onValueChange={(v) => {
                  setJobLevel(v);
                  if (errors.jobLevel) setErrors((p) => ({ ...p, jobLevel: false }));
                }}
              >
                <SelectTrigger className={`h-11.5 ${errors.jobLevel ? 'border-red-50' : ''}`}>
                  <SelectValue placeholder="선택 안됨" />
                </SelectTrigger>
                <SelectContent position="popper" side="bottom" sideOffset={4} avoidCollisions={false}>
                  {JOB_LEVEL_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.jobLevel && (
                <div className="flex items-center gap-0.5">
                  <ErrorIcon className="size-4 shrink-0 text-red-50" />
                  <span className="text-label-xsmall text-red-50">직급을 선택해주세요.</span>
                </div>
              )}
            </div>

            {/* 부서명 — MEMBER only */}
            {!isAdmin && (
              <div className="flex flex-col gap-1.5">
                <label className="text-heading-medium text-content-normal flex items-center gap-1">
                  <span className="size-1.25 rounded-full bg-red-50" />
                  부서명을 알려주세요.
                </label>
                <Select
                  value={department}
                  onValueChange={(v) => {
                    setDepartment(v);
                    if (errors.department) setErrors((p) => ({ ...p, department: false }));
                  }}
                >
                  <SelectTrigger className={`h-11.5 ${errors.department ? 'border-red-50' : ''}`}>
                    <SelectValue placeholder="선택 안됨" />
                  </SelectTrigger>
                  <SelectContent
                    position="popper"
                    side="bottom"
                    sideOffset={4}
                    avoidCollisions={false}
                    className="max-h-45"
                  >
                    {DEPARTMENT_OPTIONS.map((opt) => (
                      <SelectItem key={opt} value={opt}>
                        {opt}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.department && (
                  <div className="flex items-center gap-0.5">
                    <ErrorIcon className="size-4 shrink-0 text-red-50" />
                    <span className="text-label-xsmall text-red-50">부서명을 선택해주세요.</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <StepNavButtons onBack={onBack} onNext={handleNext} isNextDisabled={!isComplete} />
    </div>
  );
}
