'use client';

import { useState } from 'react';

import ErrorIcon from '@/public/icons/icon/error.svg';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { DEPARTMENT_OPTIONS, RANK_OPTIONS } from '@/shared/constants/organization';

import type { ProfileFormData } from '../../types/onboarding';
import { StepIndicator } from '../StepIndicator';
import { StepNavButtons } from '../StepNavButtons';

interface ProfileStepProps {
  isAdmin: boolean;
  defaultValues: {
    name: string;
    rank: string;
    department: string;
  };
  onSubmit: (data: ProfileFormData) => void;
  onBack?: () => void;
}

export function ProfileStep({ isAdmin, defaultValues, onSubmit, onBack }: ProfileStepProps) {
  const [name, setName] = useState(defaultValues.name);
  const [rank, setRank] = useState(defaultValues.rank);
  const [department, setDepartment] = useState(defaultValues.department);

  const [errors, setErrors] = useState<Record<string, boolean>>({});

  const totalSteps = 2;

  const validate = () => {
    const newErrors: Record<string, boolean> = {};
    if (!name.trim()) newErrors.name = true;
    if (!rank) newErrors.rank = true;
    if (!isAdmin && !department) newErrors.department = true;
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (!validate()) return;
    onSubmit({
      name: name.trim(),
      rank,
      ...(isAdmin ? {} : { department }),
    });
  };

  const isComplete = name.trim() && rank && (isAdmin || department);

  return (
    <div className="flex size-full flex-col justify-between">
      <div className="flex flex-col gap-12">
        {/* 헤더 영역: 스텝 인디케이터 + 타이틀 + 설명 */}
        <div className="flex flex-col gap-4">
          <StepIndicator totalSteps={totalSteps} currentStep={1} />
          <h1 className="text-display-large text-gray-80 tracking-tight">
            잠시만 시간을 내어
            <br />
            간단한 정보를 알려주세요.
          </h1>
          <p className="text-body-large tracking-tight text-gray-50">성함과 맡고 계신 역할만 알려주셔도 충분합니다.</p>
        </div>

        {/* 폼 영역 */}
        <div className="flex flex-col gap-6">
          {/* 이름 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-heading-medium text-gray-80 flex items-center gap-1 tracking-tight">
              <span className="size-[5px] rounded-full bg-red-50" />
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
              className="h-[46px]"
            />
          </div>

          {/* 직급 + 부서명 */}
          <div className={isAdmin ? '' : 'flex gap-2'}>
            <div className={`flex flex-col gap-1.5 ${isAdmin ? '' : 'flex-1'}`}>
              <label className="text-heading-medium text-gray-80 flex items-center gap-1 tracking-tight">
                <span className="size-[5px] rounded-full bg-red-50" />
                직급을 알려주세요.
              </label>
              <Select
                value={rank}
                onValueChange={(v) => {
                  setRank(v);
                  if (errors.rank) setErrors((p) => ({ ...p, rank: false }));
                }}
              >
                <SelectTrigger className={`h-[46px] ${errors.rank ? 'border-red-50' : ''}`}>
                  <SelectValue placeholder="선택 안됨" />
                </SelectTrigger>
                <SelectContent position="popper" side="bottom" sideOffset={4} avoidCollisions={false}>
                  {RANK_OPTIONS.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.rank && (
                <div className="flex items-center gap-0.5">
                  <ErrorIcon className="size-4 shrink-0 text-red-50" />
                  <span className="text-label-xsmall text-red-50">직급을 선택해주세요.</span>
                </div>
              )}
            </div>

            {/* 부서명 — MEMBER only */}
            {!isAdmin && (
              <div className="flex flex-1 flex-col gap-1.5">
                <label className="text-heading-medium text-gray-80 flex items-center gap-1 tracking-tight">
                  <span className="size-[5px] rounded-full bg-red-50" />
                  부서명을 알려주세요.
                </label>
                <Select
                  value={department}
                  onValueChange={(v) => {
                    setDepartment(v);
                    if (errors.department) setErrors((p) => ({ ...p, department: false }));
                  }}
                >
                  <SelectTrigger className={`h-[46px] ${errors.department ? 'border-red-50' : ''}`}>
                    <SelectValue placeholder="선택 안됨" />
                  </SelectTrigger>
                  <SelectContent position="popper" side="bottom" sideOffset={4} avoidCollisions={false} className="max-h-45">
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
