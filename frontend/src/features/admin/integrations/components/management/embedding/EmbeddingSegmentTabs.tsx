'use client';

import { cn } from '@/shared/utils/cn';

export type EmbeddingTabValue = 'manage' | 'status';

interface EmbeddingSegmentTabsProps {
  value: EmbeddingTabValue;
  /** 진행중인 임베딩이 있으면 현황 탭에 점이 붙는다 */
  hasRunning: boolean;
  onChange: (value: EmbeddingTabValue) => void;
}

const TABS: readonly { value: EmbeddingTabValue; label: string }[] = [
  { value: 'manage', label: '임베딩 관리' },
  { value: 'status', label: '임베딩 현황' },
];

/**
 * 커넥터 상세의 임베딩 관리 / 현황 전환.
 *
 * 진행중 점의 파랑을 정확히 주는 `bg-*` 시맨틱 토큰이 없어, 같은 값을 가진
 * 텍스트 색을 `bg-current`로 끌어써 낸다(사용자 결정).
 */
export default function EmbeddingSegmentTabs({ value, hasRunning, onChange }: EmbeddingSegmentTabsProps) {
  return (
    <div role="tablist" className="bg-fill-normal-strong flex gap-1 rounded-lg p-1">
      {TABS.map((tab) => {
        const selected = tab.value === value;
        const showDot = tab.value === 'status' && hasRunning;

        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.value)}
            className={cn(
              'text-body-small flex h-9 flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg px-4 py-1.5 transition-colors',
              /*
               * 눌림 상태가 코드에 아예 없어 터치·키보드 활성화 때 아무 반응이 없었다.
               * Figma 는 hover 와 pressed 가 같은 값이라 같은 토큰을 쓴다 —
               * 마우스로 누를 땐 색이 안 바뀐다(디자이너 확인 필요).
               */
              selected
                ? 'bg-fill-normal-normal text-text-normal-normal'
                : 'text-text-normal-alternative hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-hover',
            )}
          >
            {tab.label}
            {showDot && (
              <>
                <span aria-hidden="true" className="text-icon-primary-assistive size-1.5 rounded-full bg-current" />
                <span className="sr-only">진행 중</span>
              </>
            )}
          </button>
        );
      })}
    </div>
  );
}
