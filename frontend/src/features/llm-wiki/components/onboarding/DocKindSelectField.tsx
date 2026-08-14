'use client';

import type { FC, SVGProps } from 'react';

import IconBook from '@/public/icons/icon/book.svg';
import IconClient from '@/public/icons/icon/building.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconError from '@/public/icons/icon/error.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconHelp from '@/public/icons/icon/help.svg';
import IconHistory from '@/public/icons/icon/history.svg';
import IconRequest from '@/public/icons/icon/tree.svg';

import type { KnownDocKindIcon, WikiDocKindPreset } from '../../types/llmWikiOnboarding';
import OnboardingFieldLabel from './OnboardingFieldLabel';

// request·client는 시안 자산이 리포에 없어 근접 자산으로 대체했다(감사 §7)
const DOC_KIND_ICONS: Record<KnownDocKindIcon, FC<SVGProps<SVGSVGElement>>> = {
  request: IconRequest,
  error: IconError,
  help: IconHelp,
  client: IconClient,
  history: IconHistory,
  book: IconBook,
};

interface DocKindSelectFieldProps {
  label: string;
  presets: readonly WikiDocKindPreset[];
  selectedId: string | null;
  onSelect?: (id: string) => void;
  sampleTitle: string;
  /** 목적이 수집 범위에 영향 없다는 오해 방지 카피 — 8/14 시안에서 이 헤더로 이동했다 */
  sampleCaption: string;
  sampleText: string;
}

// 문서 종류 단일 선택 리스트(스크롤) + 템플릿 예시 패널
export default function DocKindSelectField({
  label,
  presets,
  selectedId,
  onSelect,
  sampleTitle,
  sampleCaption,
  sampleText,
}: DocKindSelectFieldProps) {
  return (
    <div className="flex w-full flex-col gap-3">
      <OnboardingFieldLabel label={label} required />

      <div className="border-line-normal-neutral grid grid-cols-[400fr_606fr] overflow-hidden rounded-xl border">
        <div
          role="radiogroup"
          aria-label={label}
          className="custom-scrollbar flex max-h-125 min-w-0 flex-col gap-3 overflow-y-auto p-4"
        >
          {presets.map((preset) => {
            const checked = preset.id === selectedId;
            const Icon = DOC_KIND_ICONS[preset.icon as KnownDocKindIcon] ?? IconFile;

            return (
              <button
                key={preset.id}
                type="button"
                role="radio"
                aria-checked={checked}
                onClick={() => onSelect?.(preset.id)}
                className="border-line-normal-neutral hover:bg-fill-normal-interaction-hover flex w-full shrink-0 cursor-pointer items-start justify-between gap-3 rounded-xl border p-4 text-left transition-colors"
              >
                <span className="flex min-w-0 flex-col gap-2">
                  <span className="flex items-center gap-2">
                    <Icon className="text-icon-normal-normal size-5 shrink-0" />
                    <span className="text-heading-small text-text-normal-normal truncate">{preset.label}</span>
                  </span>
                  <span className="text-body-small text-text-normal-alternative">{preset.description}</span>
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

        <div className="border-line-normal-neutral flex min-w-0 flex-col border-l">
          <div className="border-line-normal-neutral flex items-center gap-2 border-b px-8 py-3">
            <IconFile className="text-icon-normal-normal size-5 shrink-0" />
            <span className="text-body-small text-text-normal-normal shrink-0">{sampleTitle}</span>
            <span className="text-label-xsmall text-text-normal-alternative min-w-0 flex-1 truncate text-right">
              {sampleCaption}
            </span>
          </div>
          <p className="text-body-small text-text-normal-alternative px-8 py-6">{sampleText}</p>
        </div>
      </div>
    </div>
  );
}
