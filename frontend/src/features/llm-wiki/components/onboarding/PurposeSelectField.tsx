'use client';

import IconAddCircleFilled from '@/public/icons/icon/add_circle_filled.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import { cn } from '@/shared/utils/cn';

import type { WikiPurposeOption } from '../../types/llmWikiOnboarding';
import OnboardingFieldLabel from './OnboardingFieldLabel';

interface PurposeSelectFieldProps {
  label: string;
  /** 라벨 우측 안내 카피 — 목적이 수집 범위에 영향 없다는 오해 방지 문구 */
  caption: string;
  options: readonly WikiPurposeOption[];
  selectedId: string | null;
  onSelect?: (id: string) => void;
  followUpValue: string;
  onFollowUpChange?: (next: string) => void;
  followUpPlaceholder: string;
  followUpMaxLength: number;
  /** 후속 질문 아래 예시 카피 — 없으면 줄 자체를 그리지 않는다 */
  followUpExample?: string;
}

// 목적 단일 선택 + 선택별 후속 질문. 커스텀의 후속 UI는 시안에 없어 질문 null이면 패널을 접는다
export default function PurposeSelectField({
  label,
  caption,
  options,
  selectedId,
  onSelect,
  followUpValue,
  onFollowUpChange,
  followUpPlaceholder,
  followUpMaxLength,
  followUpExample,
}: PurposeSelectFieldProps) {
  const selected = options.find((option) => option.id === selectedId) ?? null;

  return (
    <div className="flex w-full flex-col gap-3">
      <div className="flex items-end justify-between gap-4">
        <OnboardingFieldLabel label={label} required />
        <span className="text-label-xsmall text-text-normal-alternative truncate">{caption}</span>
      </div>

      <div
        role="radiogroup"
        aria-label={label}
        className="border-line-normal-neutral divide-line-normal-neutral divide-y overflow-hidden rounded-xl border"
      >
        {options.map((option) => {
          const checked = option.id === selectedId;

          return (
            <button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={checked}
              onClick={() => onSelect?.(option.id)}
              className="hover:bg-fill-normal-interaction-hover flex h-14 w-full cursor-pointer items-center justify-between gap-4 px-4 text-left transition-colors"
            >
              <span className="text-body-small text-text-normal-normal truncate">{option.label}</span>
              {checked ? (
                <IconCheckCircleFilled className="text-icon-primary-normal size-6 shrink-0" />
              ) : (
                <IconCheckCircle className="text-icon-normal-alternative size-6 shrink-0" />
              )}
            </button>
          );
        })}
      </div>

      {selected?.followUpQuestion && (
        <div className="bg-fill-normal-strong flex flex-col gap-2.5 rounded-2xl p-5">
          <div className="flex items-center gap-2.5">
            <IconAddCircleFilled className="text-icon-primary-normal size-6 shrink-0" />
            <span className="text-body-small text-text-normal-normal min-w-0 truncate">{selected.followUpQuestion}</span>
          </div>
          <div className="bg-fill-normal-normal flex flex-col gap-2.5 rounded-xl p-4">
            <textarea
              rows={1}
              value={followUpValue}
              maxLength={followUpMaxLength}
              placeholder={followUpPlaceholder}
              aria-label={selected.followUpQuestion}
              onChange={(event) => onFollowUpChange?.(event.target.value)}
              className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive w-full resize-none bg-transparent outline-none"
            />
            <span className="text-body-small text-text-normal-assistive">
              {followUpValue.length}/{followUpMaxLength}
            </span>
          </div>
          {followUpExample && (
            <span className={cn('text-label-xsmall text-text-normal-assistive')}>{followUpExample}</span>
          )}
        </div>
      )}
    </div>
  );
}
