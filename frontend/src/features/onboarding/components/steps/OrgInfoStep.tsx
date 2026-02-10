'use client';

import { useState } from 'react';

import ErrorIcon from '@/public/icons/icon/error.svg';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';

import { TEAM_SIZE_OPTIONS } from '../../constants/onboarding';
import type { OrgInfoFormData } from '../../types/onboarding';
import { StepIndicator } from '../StepIndicator';
import { StepNavButtons } from '../StepNavButtons';

interface OrgInfoStepProps {
  defaultValues: {
    company_name: string;
    team_size: string;
  };
  onSubmit: (data: OrgInfoFormData) => void;
  onBack: () => void;
}

export function OrgInfoStep({ defaultValues, onSubmit, onBack }: OrgInfoStepProps) {
  const [companyName, setCompanyName] = useState(defaultValues.company_name);
  const [teamSize, setTeamSize] = useState(defaultValues.team_size);

  const [errors, setErrors] = useState<Record<string, boolean>>({});

  const validate = () => {
    const newErrors: Record<string, boolean> = {};
    if (!companyName.trim()) newErrors.companyName = true;
    if (!teamSize) newErrors.teamSize = true;
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (!validate()) return;
    onSubmit({ company_name: companyName.trim(), team_size: teamSize });
  };

  const isComplete = companyName.trim() && teamSize;

  return (
    <div className="flex h-full w-[441px] flex-col justify-between">
      <div className="flex flex-col gap-12">
        {/* 헤더 영역: 스텝 인디케이터 + 타이틀 + 설명 */}
        <div className="flex flex-col gap-4">
          <StepIndicator totalSteps={2} currentStep={2} />
          <h1 className="text-display-large tracking-tight text-gray-80">
            회사에 대해
            <br />
            조금만 알려주세요!
          </h1>
          <p className="text-body-large tracking-tight text-gray-50">
            팀 구성에 따라 더 정확한 인수인계 경험을
            <br />
            준비해드릴게요.
          </p>
        </div>

        {/* 폼 영역 */}
        <div className="flex flex-col gap-6">
          {/* 회사명 */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-heading-medium tracking-tight text-gray-80">
              <span className="size-[5px] rounded-full bg-red-50" />
              회사명을 알려주세요.
            </label>
            <Input
              value={companyName}
              onChange={(e) => {
                setCompanyName(e.target.value);
                if (errors.companyName) setErrors((p) => ({ ...p, companyName: false }));
              }}
              placeholder="회사명"
              error={errors.companyName}
              className="h-[46px]"
            />
          </div>

          {/* 팀 규모 */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-heading-medium tracking-tight text-gray-80">
              <span className="size-[5px] rounded-full bg-red-50" />
              팀 규모는 어느 정도인가요?
            </label>
            <Select
              value={teamSize}
              onValueChange={(v) => {
                setTeamSize(v);
                if (errors.teamSize) setErrors((p) => ({ ...p, teamSize: false }));
              }}
            >
              <SelectTrigger className={`h-[46px] ${errors.teamSize ? 'border-red-50' : ''}`}>
                <SelectValue placeholder="선택 안됨" />
              </SelectTrigger>
              <SelectContent>
                {TEAM_SIZE_OPTIONS.map((opt) => (
                  <SelectItem key={opt} value={opt}>
                    {opt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.teamSize && (
              <div className="flex items-center gap-0.5">
                <ErrorIcon className="size-4 shrink-0 text-red-50" />
                <span className="text-label-xsmall text-red-50">팀 규모를 선택해주세요.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <StepNavButtons
        onBack={onBack}
        onNext={handleNext}
        isNextDisabled={!isComplete}
      />
    </div>
  );
}
