'use client';

import type { FC, SVGProps } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

import IconBook from '@/public/icons/icon/book.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconCheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import IconClient from '@/public/icons/icon/client.svg';
import IconError from '@/public/icons/icon/error.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconHelp from '@/public/icons/icon/help.svg';
import IconHistory from '@/public/icons/icon/history.svg';
import IconRequest from '@/public/icons/icon/request.svg';
import { cn } from '@/shared/utils/cn';

import type { KnownDocKindIcon, WikiDocKindPreset } from '../../types/llmWikiOnboarding';
import OnboardingFieldLabel from './OnboardingFieldLabel';

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
  /** 선택한 종류의 문서 양식(마크다운) */
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
            const disabled = preset.disabled === true;
            const Icon = DOC_KIND_ICONS[preset.icon as KnownDocKindIcon] ?? IconFile;

            return (
              <button
                key={preset.id}
                type="button"
                role="radio"
                aria-checked={checked}
                disabled={disabled}
                onClick={() => onSelect?.(preset.id)}
                className={cn(
                  'border-line-normal-neutral flex w-full shrink-0 items-start gap-5 rounded-xl border p-4 text-left transition-colors',
                  disabled
                    ? 'border-line-normal-normal bg-fill-normal-interaction-inactive cursor-not-allowed'
                    : 'hover:bg-fill-normal-interaction-hover cursor-pointer',
                )}
              >
                <span className="flex min-w-0 flex-1 flex-col gap-2">
                  <span className="flex items-center gap-2">
                    <Icon
                      className={cn(
                        'size-5 shrink-0',
                        disabled ? 'text-icon-normal-assistive' : 'text-icon-primary-normal',
                      )}
                    />
                    <span
                      className={cn(
                        'text-heading-small truncate',
                        disabled ? 'text-text-normal-assistive' : 'text-text-normal-normal',
                      )}
                    >
                      {preset.label}
                    </span>
                  </span>
                  {/* 줄바꿈은 띄어쓰기 단위로만 — 한글은 기본값이면 단어 중간에서도 끊긴다 */}
                  <span
                    className={cn(
                      'text-body-small break-keep',
                      disabled ? 'text-text-normal-assistive' : 'text-text-normal-alternative',
                    )}
                  >
                    {preset.description}
                  </span>
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

        <div className="border-line-normal-neutral flex max-h-125 min-w-0 flex-col border-l">
          <div className="border-line-normal-neutral flex shrink-0 items-center gap-2 border-b px-8 py-3">
            <IconFile className="text-icon-normal-normal size-5 shrink-0" />
            <span className="text-body-small text-text-normal-normal shrink-0">{sampleTitle}</span>
            <span className="text-label-xsmall text-text-normal-alternative min-w-0 flex-1 truncate text-right">
              {sampleCaption}
            </span>
          </div>
          {/* 양식은 마크다운이라 표·인용이 있다 — 공용 markdown.css의 읽기 변형으로 렌더한다 */}
          <div className="markdown-body markdown-reading custom-scrollbar min-h-0 flex-1 overflow-y-auto px-8 py-6 wrap-break-word">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{sampleText}</ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
