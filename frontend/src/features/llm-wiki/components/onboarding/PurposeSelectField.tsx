'use client';

import type { FC, SVGProps } from 'react';

import IconAddCircleFilled from '@/public/icons/icon/add_circle_filled.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconClient from '@/public/icons/icon/client.svg';
import IconDatabase from '@/public/icons/icon/database.svg';
import IconGroup from '@/public/icons/icon/group.svg';
import IconLightbulb from '@/public/icons/icon/lightbulb.svg';
import IconShield from '@/public/icons/icon/shield.svg';
import IconSupportAgent from '@/public/icons/icon/support_agent.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import { cn } from '@/shared/utils/cn';

import type { KnownInfoCategoryIcon, WikiInfoCategory } from '../../types/llmWikiOnboarding';
import OnboardingFieldLabel from './OnboardingFieldLabel';

const CATEGORY_ICONS: Record<KnownInfoCategoryIcon, FC<SVGProps<SVGSVGElement>>> = {
  'support-agent': IconSupportAgent,
  lightbulb: IconLightbulb,
  shield: IconShield,
  client: IconClient,
  database: IconDatabase,
  group: IconGroup,
};

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
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-col gap-5">
        <OnboardingFieldLabel label={categoryLabel} required />
        <div role="radiogroup" aria-label={categoryLabel} className="flex flex-wrap items-center gap-3">
          {categories.map((category) => {
            const checked = category.id === selectedCategoryId;
            const Icon = CATEGORY_ICONS[category.icon as KnownInfoCategoryIcon] ?? IconTag;

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
                    : 'border-line-normal-neutral text-text-normal-neutral hover:bg-fill-normal-interaction-hover border',
                )}
              >
                <Icon
                  className={cn('size-5 shrink-0', checked ? 'text-icon-normal-inverse' : 'text-icon-normal-normal')}
                />
                {category.label}
              </button>
            );
          })}
        </div>
      </div>

      {purposeOptions.length > 0 && (
        <div className="flex gap-4">
          {/* 들여쓰기 가이드 — 폭 32의 중앙에 2px 점선이 세로로 지난다 */}
          <div className="flex w-8 shrink-0 justify-center">
            <span className="border-line-normal-normal h-full border-l-2 border-dashed" />
          </div>

          <div className="flex min-w-0 flex-1 flex-col gap-3">
            <div className="flex items-center gap-2">
              <IconAddCircleFilled className="text-icon-normal-neutral size-5 shrink-0" />
              <OnboardingFieldLabel label={purposeLabel} required size="body" />
            </div>

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
                    className="border-line-normal-neutral hover:bg-fill-normal-interaction-hover flex min-w-0 cursor-pointer items-start gap-6 rounded-xl border p-4 text-left transition-colors"
                  >
                    {/* 줄바꿈은 띄어쓰기 단위로만 — 한글은 기본값이면 단어 중간에서도 끊긴다 */}
                    <span className="text-body-small text-text-normal-neutral min-w-0 flex-1 break-keep">
                      {option.label}
                    </span>
                    {checked ? (
                      <IconCheckCircleFilled className="text-icon-primary-normal size-6 shrink-0" />
                    ) : (
                      <IconCheckCircle className="text-icon-normal-assistive size-6 shrink-0" />
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
