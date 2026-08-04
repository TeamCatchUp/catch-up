'use client';

import type { ComponentType, SVGProps } from 'react';

import { cn } from '@/shared/utils/cn';

interface MappingStatCardProps {
  /** 커넥터 브랜드 로고 (`CONNECTOR_LOGOS`) */
  Logo: ComponentType<SVGProps<SVGSVGElement>>;
  name: string;
  /** 완료율(%). 정수로 반올림해 넘긴다 */
  percent: number;
  /** "65/100" 형태의 건수 */
  countLabel: string;
  /** 눌러서 아래 표를 이 커넥터로 필터 */
  selected: boolean;
  onToggle: () => void;
}

/**
 * 계정 등록 상태 카드 1장.
 * Figma `17300:80305` — p 20, gap 20, 로고칩 48(p 8, radius 12, fill/normal/strong,
 * 로고 28), 이름·완료율 heading-small, 건수 Tag(fill/primary/normal/neutral,
 * px 6 py 2, radius 6, 13px text/primary/normal).
 *
 * 카드 폭 208은 행 1040의 5등분이라 박지 않는다 — 행이 5등분한다.
 * selected 시각 변형은 Figma에 없어(감사 B-2 UNKNOWN) 발명하지 않고
 * `aria-pressed`만 노출한다 — 필터 결과는 아래 칩과 표가 보여준다.
 */
export default function MappingStatCard({ Logo, name, percent, countLabel, selected, onToggle }: MappingStatCardProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      className="hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex min-w-0 flex-1 cursor-pointer items-center gap-5 p-5 text-left transition-colors"
    >
      <span className="bg-fill-normal-strong flex size-12 shrink-0 items-center justify-center rounded-xl p-2">
        <Logo className="size-7" />
      </span>
      <span className="flex min-w-0 flex-col gap-1">
        <span className="text-heading-small text-text-normal-normal truncate">{name}</span>
        <span className="flex items-center gap-2">
          <span className="text-heading-small text-text-normal-neutral">{percent}%</span>
          <span
            className={cn(
              'bg-fill-primary-normal-neutral text-body-xsmall text-text-primary-normal rounded-md2 px-1.5 py-0.5 whitespace-nowrap',
            )}
          >
            {countLabel}
          </span>
        </span>
      </span>
    </button>
  );
}
