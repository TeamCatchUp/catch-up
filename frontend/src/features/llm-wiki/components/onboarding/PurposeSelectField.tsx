'use client';

import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import { cn } from '@/shared/utils/cn';

import type { WikiInfoCategory } from '../../types/llmWikiOnboarding';
import OnboardingFieldLabel from './OnboardingFieldLabel';

interface PurposeSelectFieldProps {
  categoryLabel: string;
  categories: readonly WikiInfoCategory[];
  selectedCategoryId: string | null;
  onSelectCategory?: (id: string) => void;
  purposeLabel: string;
  selectedPurposeId: string | null;
  onSelectPurpose?: (id: string) => void;
}

// 정보 카테고리 칩 + 선택한 카테고리의 목적 선택. 목적이 없는 카테고리는 분기 구역을 접는다
export default function PurposeSelectField({
  categoryLabel,
  categories,
  selectedCategoryId,
  onSelectCategory,
  purposeLabel,
  selectedPurposeId,
  onSelectPurpose,
}: PurposeSelectFieldProps) {
  const selectedCategory = categories.find((category) => category.id === selectedCategoryId) ?? null;
  const purposeOptions = selectedCategory?.purposeOptions ?? [];

  return (
    <div className="flex w-full flex-col gap-7">
      <div className="flex flex-col gap-3">
        <OnboardingFieldLabel label={categoryLabel} required />
        <div role="radiogroup" aria-label={categoryLabel} className="flex flex-wrap gap-3">
          {categories.map((category) => {
            const checked = category.id === selectedCategoryId;

            return (
              <button
                key={category.id}
                type="button"
                role="radio"
                aria-checked={checked}
                onClick={() => onSelectCategory?.(category.id)}
                className={cn(
                  'text-body-small flex h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors',
                  checked
                    ? 'bg-accent-black-lighten text-text-normal-inverse'
                    : 'border-line-normal-normal text-text-normal-neutral hover:bg-fill-normal-interaction-hover border',
                )}
              >
                <IconTag
                  className={cn('size-5 shrink-0', checked ? 'text-icon-normal-inverse' : 'text-icon-normal-normal')}
                />
                {category.label}
              </button>
            );
          })}
        </div>
      </div>

      {purposeOptions.length > 0 && (
        <div className="border-line-normal-neutral flex border-l pl-8">
          <IconArrowRight2 className="text-icon-normal-alternative mt-6 size-6 shrink-0" />
          <div className="flex min-w-0 flex-1 flex-col gap-3 pl-4">
            <OnboardingFieldLabel label={purposeLabel} required size="body" />
            <div role="radiogroup" aria-label={purposeLabel} className="grid grid-cols-3 gap-4">
              {purposeOptions.map((option) => {
                const checked = option.id === selectedPurposeId;

                return (
                  <button
                    key={option.id}
                    type="button"
                    role="radio"
                    aria-checked={checked}
                    onClick={() => onSelectPurpose?.(option.id)}
                    className="border-line-normal-neutral hover:bg-fill-normal-interaction-hover flex min-w-0 cursor-pointer items-start justify-between gap-3 rounded-xl border p-4 text-left transition-colors"
                  >
                    <span className="text-body-small text-text-normal-normal min-w-0">{option.label}</span>
                    {checked ? (
                      <IconCheckCircleFilled className="text-icon-primary-normal size-6 shrink-0" />
                    ) : (
                      <IconCheckCircle className="text-icon-normal-alternative size-6 shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
