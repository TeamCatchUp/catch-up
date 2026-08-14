'use client';

import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';

import type { WikiToneStyleOption } from '../../types/llmWikiOnboarding';
import OnboardingFieldLabel from './OnboardingFieldLabel';

interface ToneStyleFieldProps {
  label: string;
  options: readonly WikiToneStyleOption[];
  selectedId: string | null;
  onSelect?: (id: string) => void;
  /** 예시 문장 앞에 붙는 태그 라벨 */
  sampleTagLabel: string;
}

// 문체 단일 선택 3열 카드. 각 카드가 자기 예시 문장을 함께 보여준다
export default function ToneStyleField({ label, options, selectedId, onSelect, sampleTagLabel }: ToneStyleFieldProps) {
  return (
    <div className="flex w-full flex-col gap-3">
      <OnboardingFieldLabel label={label} required />

      <div role="radiogroup" aria-label={label} className="grid grid-cols-3 gap-4">
        {options.map((option) => {
          const checked = option.id === selectedId;

          return (
            <button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={checked}
              onClick={() => onSelect?.(option.id)}
              className="border-line-normal-neutral hover:bg-fill-normal-interaction-hover flex min-w-0 cursor-pointer flex-col gap-5 rounded-xl border p-4 text-left transition-colors"
            >
              <span className="flex items-start justify-between gap-3">
                <span className="flex min-w-0 flex-col gap-2">
                  <span className="text-heading-small text-text-normal-normal truncate">{option.label}</span>
                  <span className="text-body-small text-text-normal-alternative">{option.description}</span>
                </span>
                {checked ? (
                  <IconCheckCircleFilled className="text-icon-primary-normal size-6 shrink-0" />
                ) : (
                  <IconCheckCircle className="text-icon-normal-assistive size-6 shrink-0" />
                )}
              </span>

              <span className="flex flex-col gap-2">
                <span className="bg-accent-light-blue-neutral text-text-normal-normal text-body-xsmall rounded-md2 w-fit px-1.5 py-0.5">
                  {sampleTagLabel}
                </span>
                <span className="text-body-small text-text-normal-alternative">{option.sampleText}</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
