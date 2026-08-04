'use client';

import { Chip } from '@/shared/components/ui/chips';

/** API status 필터와 1:1 — all/full/partial (`userSourceMappingApi.ts`) */
export type MappingStatusFilter = 'all' | 'full' | 'partial';

const FILTERS: readonly { value: MappingStatusFilter; label: string }[] = [
  { value: 'all', label: '전체 이용자' },
  { value: 'full', label: '전체 연동됨' },
  { value: 'partial', label: '일부 미연동' },
];

interface MappingFilterChipsProps {
  value: MappingStatusFilter;
  onChange: (next: MappingStatusFilter) => void;
  /** 통계 카드 탭으로 걸린 커넥터 필터 — 있으면 네 번째 칩으로 나타난다 */
  sourceLabel?: string | null;
  onClearSource?: () => void;
}

/**
 * 계정 매핑 상태 필터 칩.
 * Figma `17379:78312` 좌측 — 임베딩 히스토리 필터와 같은 낱개 칩 토글이라
 * `Chip variant="outline"`을 그대로 쓴다. 칩 마스터 라벨은 플레이스홀더(✏️ Value)라
 * 라벨은 화면 스크린샷 실측이다.
 *
 * 커넥터 칩은 통계 카드 탭이 만든다 — 칩을 다시 누르면 커넥터 필터 해제.
 */
export default function MappingFilterChips({ value, onChange, sourceLabel, onClearSource }: MappingFilterChipsProps) {
  return (
    <div role="tablist" className="flex flex-wrap gap-1">
      {FILTERS.map((option) => (
        <Chip
          key={option.value}
          variant="outline"
          selected={option.value === value && !sourceLabel}
          role="tab"
          aria-selected={option.value === value && !sourceLabel}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </Chip>
      ))}
      {sourceLabel && (
        <Chip variant="outline" selected role="tab" aria-selected onClick={onClearSource}>
          {sourceLabel}
        </Chip>
      )}
    </div>
  );
}
