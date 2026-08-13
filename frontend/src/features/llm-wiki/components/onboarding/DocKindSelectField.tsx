'use client';

import type { FC, SVGProps } from 'react';

import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconGraph from '@/public/icons/icon/graph.svg';
import IconGroup from '@/public/icons/icon/group.svg';
import IconSearchFile from '@/public/icons/icon/search_file.svg';

import type { KnownDocKindIcon, WikiDocKindPreset } from '../../types/llmWikiOnboarding';
import OnboardingFieldLabel from './OnboardingFieldLabel';

const DOC_KIND_ICONS: Record<KnownDocKindIcon, FC<SVGProps<SVGSVGElement>>> = {
  file: IconFile,
  group: IconGroup,
  graph: IconGraph,
  'search-file': IconSearchFile,
};

interface DocKindSelectFieldProps {
  label: string;
  presets: readonly WikiDocKindPreset[];
  selectedId: string | null;
  onSelect?: (id: string) => void;
  sampleTitle: string;
  /** 우측 패널의 예시 문장 — 선택과의 연동 규칙은 부모가 정한다 */
  sampleText: string;
}

// 문서 종류 단일 선택 리스트 + 예시 문장 패널
export default function DocKindSelectField({
  label,
  presets,
  selectedId,
  onSelect,
  sampleTitle,
  sampleText,
}: DocKindSelectFieldProps) {
  return (
    <div className="flex w-full flex-col gap-3">
      <OnboardingFieldLabel label={label} required />

      <div className="border-line-normal-neutral grid grid-cols-[2fr_3fr] overflow-hidden rounded-xl border">
        <div role="radiogroup" aria-label={label} className="flex min-w-0 flex-col gap-4 p-4">
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
                className="border-line-normal-neutral hover:bg-fill-normal-interaction-hover flex w-full cursor-pointer items-center justify-between gap-3 rounded-xl border p-4 text-left transition-colors"
              >
                <span className="flex min-w-0 flex-col gap-2">
                  <span className="flex items-center gap-2">
                    <Icon className="text-icon-normal-normal size-5 shrink-0" />
                    <span className="text-body-small text-text-normal-normal truncate">{preset.label}</span>
                  </span>
                  <span className="text-label-xsmall text-text-normal-alternative">{preset.description}</span>
                </span>
                {checked ? (
                  <IconCheckCircleFilled className="text-icon-primary-normal size-6 shrink-0" />
                ) : (
                  <IconCheckCircle className="text-icon-normal-alternative size-6 shrink-0" />
                )}
              </button>
            );
          })}
        </div>

        <div className="border-line-normal-neutral flex min-w-0 flex-col gap-6 border-l p-8">
          <span className="text-heading-small text-text-normal-normal">{sampleTitle}</span>
          <p className="text-body-small text-text-normal-alternative">{sampleText}</p>
        </div>
      </div>
    </div>
  );
}
