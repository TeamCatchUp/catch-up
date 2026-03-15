'use client';

import { useState } from 'react';

import ErrorIcon from '@/public/icons/icon/error.svg';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { COMPANY_SIZE_OPTIONS } from '@/shared/constants/organization';

import type { CompanySize, OrgInfoFormData } from '../../types/onboarding';
import { StepIndicator } from '../StepIndicator';
import { StepNavButtons } from '../StepNavButtons';

interface OrgInfoStepProps {
  defaultValues: {
    company_name: string;
    company_size: string;
  };
  onSubmit: (data: OrgInfoFormData) => void;
  onBack: (data: OrgInfoFormData) => void;
}

export function OrgInfoStep({ defaultValues, onSubmit, onBack }: OrgInfoStepProps) {
  const [companyName, setCompanyName] = useState(defaultValues.company_name);
  const [companySize, setCompanySize] = useState(defaultValues.company_size);

  const [errors, setErrors] = useState<Record<string, boolean>>({});

  const validate = () => {
    const newErrors: Record<string, boolean> = {};
    if (!companyName.trim()) newErrors.companyName = true;
    if (!companySize) newErrors.companySize = true;
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (!validate()) return;
    onSubmit({ company_name: companyName.trim(), company_size: companySize as CompanySize });
  };

  const isComplete = companyName.trim() && companySize;

  return (
    <div className="flex h-full w-[441px] flex-col justify-between">
      <div className="flex flex-col gap-12">
        {/* 헤더 영역: 스텝 인디케이터 + 타이틀 + 설명 */}
        <div className="flex flex-col gap-4">
          <StepIndicator totalSteps={2} currentStep={2} />
          <h1 className="text-display-large text-content-normal tracking-tight">
            회사에 대해
            <br />
            조금만 알려주세요!
          </h1>
          <p className="text-body-large text-content-alternative tracking-tight">
            팀 구성에 따라 더 정확한 인수인계 경험을
            <br />
            준비해드릴게요.
          </p>
        </div>

        {/* 폼 영역 */}
        <div className="flex flex-col gap-6">
          {/* 회사명 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-heading-medium text-content-normal flex items-center gap-1 tracking-tight">
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
            <label className="text-heading-medium text-content-normal flex items-center gap-1 tracking-tight">
              <span className="size-[5px] rounded-full bg-red-50" />팀 규모는 어느 정도인가요?
            </label>
            <Select
              value={companySize}
              onValueChange={(v) => {
                setCompanySize(v);
                if (errors.companySize) setErrors((p) => ({ ...p, companySize: false }));
              }}
            >
              <SelectTrigger className={`h-[46px] ${errors.companySize ? 'border-red-50' : ''}`}>
                <SelectValue placeholder="선택 안됨" />
              </SelectTrigger>
              <SelectContent>
                {COMPANY_SIZE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.companySize && (
              <div className="flex items-center gap-0.5">
                <ErrorIcon className="size-4 shrink-0 text-red-50" />
                <span className="text-label-xsmall text-red-50">팀 규모를 선택해주세요.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <StepNavButtons
        onBack={() => onBack({ company_name: companyName.trim(), company_size: companySize as CompanySize })}
        onNext={handleNext}
        isNextDisabled={!isComplete}
      />
    </div>
  );
}
