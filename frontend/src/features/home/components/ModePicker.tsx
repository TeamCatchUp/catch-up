'use client';

// 홈/search 페이지 히어로 모드 전환 picker (캐치스턴트 AI / 문서 탐색).
// URL `mode` 파라미터를 토글하고, 활성 배경은 layoutId로 좌우 슬라이드한다.

import { motion } from 'motion/react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import ChatFilled from '@/public/icons/icon/chat2_filled.svg';
import DocumentSearchFilled from '@/public/icons/icon/document_search_filled.svg';
import { cn } from '@/shared/utils/cn';

export type HomeMode = 'ai' | 'docs';

interface ModePickerProps {
  mode: HomeMode;
}

const OPTIONS: ReadonlyArray<{
  value: HomeMode;
  label: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
}> = [
  { value: 'ai', label: '캐치스턴트 AI', Icon: ChatFilled },
  { value: 'docs', label: '문서 탐색', Icon: DocumentSearchFilled },
];

export default function ModePicker({ mode }: ModePickerProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const handleSelect = (next: HomeMode) => {
    if (next === mode) return;
    const params = new URLSearchParams(searchParams.toString());
    if (next === 'docs') {
      params.set('mode', 'docs');
    } else {
      params.delete('mode');
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  };

  return (
    <div
      role="tablist"
      aria-label="모드 선택"
      className="border-edge-normal bg-fill-strong rounded-rounded relative flex items-center justify-center border p-0.5"
    >
      {OPTIONS.map((opt) => {
        const isActive = opt.value === mode;
        return (
          <button
            key={opt.value}
            role="tab"
            type="button"
            aria-selected={isActive}
            onClick={() => handleSelect(opt.value)}
            className={cn(
              'rounded-rounded relative inline-flex w-36.25 cursor-pointer items-center justify-center gap-2 px-4 py-2 transition-colors duration-200',
              isActive ? 'text-content-strong' : 'text-content-assistive',
            )}
          >
            {isActive && (
              <motion.span
                layoutId="mode-picker-active"
                aria-hidden
                className="rounded-rounded bg-fill-normal border-edge-strong shadow-button absolute inset-0 border"
                transition={{ type: 'spring', stiffness: 500, damping: 38 }}
              />
            )}
            <opt.Icon className="relative z-10 h-6 w-6 shrink-0" />
            <span className="text-heading-small relative z-10 whitespace-nowrap">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
