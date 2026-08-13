'use client';

import IconFile from '@/public/icons/icon/file.svg';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';

import type { WikiToneStyleOption } from '../../types/llmWikiOnboarding';
import OnboardingFieldLabel from './OnboardingFieldLabel';

interface ToneStyleFieldProps {
  label: string;
  options: readonly WikiToneStyleOption[];
  /** 체크박스형 카드라 선택을 목록으로 받는다 — 다중 허용 여부는 미확정 */
  selectedIds: readonly string[];
  onToggle?: (id: string) => void;
  customLabel: string;
  customDescription: string;
  customValue: string;
  onCustomChange?: (next: string) => void;
  customPlaceholder: string;
  customMaxLength: number;
}

// 문체 카드 선택 + 커스텀 작성 입력. 카드 썸네일은 시안에서도 빈 자리라 배경만 그린다
export default function ToneStyleField({
  label,
  options,
  selectedIds,
  onToggle,
  customLabel,
  customDescription,
  customValue,
  onCustomChange,
  customPlaceholder,
  customMaxLength,
}: ToneStyleFieldProps) {
  return (
    <div className="flex w-full flex-col gap-3">
      <OnboardingFieldLabel label={label} required />

      <div className="grid grid-cols-4 gap-6">
        {options.map((option) => {
          const checked = selectedIds.includes(option.id);

          return (
            <button
              key={option.id}
              type="button"
              role="checkbox"
              aria-checked={checked}
              onClick={() => onToggle?.(option.id)}
              className="flex min-w-0 cursor-pointer flex-col gap-4 text-left"
            >
              <span className="bg-fill-normal-strong relative block h-35 w-full rounded-lg">
                <CheckboxIcon checked={checked} className="size-5" wrapperClassName="absolute top-2 right-2" />
              </span>
              <span className="flex items-center gap-2">
                <IconFile className="text-icon-normal-normal size-5 shrink-0" />
                <span className="text-body-small text-text-normal-normal truncate">{option.label}</span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="border-line-normal-neutral flex flex-col gap-4 rounded-2xl border p-4">
        <div className="flex flex-col gap-3">
          <span className="text-body-small text-text-normal-normal">{customLabel}</span>
          <span className="text-body-small text-text-normal-alternative">{customDescription}</span>
        </div>
        <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col gap-2.5 rounded-xl border p-4">
          <textarea
            rows={8}
            value={customValue}
            maxLength={customMaxLength}
            placeholder={customPlaceholder}
            aria-label={customLabel}
            onChange={(event) => onCustomChange?.(event.target.value)}
            className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive w-full resize-none bg-transparent outline-none"
          />
          <span className="text-body-small text-text-normal-assistive">
            {customValue.length}/{customMaxLength}
          </span>
        </div>
      </div>
    </div>
  );
}
